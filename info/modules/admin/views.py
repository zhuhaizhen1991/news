import time
from datetime import datetime, timedelta

from flask import request, render_template, current_app, url_for, redirect, session, g, abort, jsonify

from info import db
from info.modules.admin import admin_blu
from info.utils.common import user_login_data, file_upload
from info.utils.constants import USER_COLLECTION_MAX_NEWS, QINIU_DOMIN_PREFIX
from info.utils.models import User, News, Category
from info.utils.response_code import RET, error_map


@admin_blu.route('/login',methods=['GET','POST'])
def login():
    if request.method == 'GET': #GET 展示页面

        #取出session数据
        user_id = session.get('user_id')
        is_admin = session.get('is_admin')
        if user_id and is_admin: #管理员已登录,重定向到后台首页
            return redirect(url_for('admin.index'))

        return render_template('admin/login.html')


    #POST 提交资料
    #获取参数
    username = request.form.get('username')
    password = request.form.get('password')
    #校验参数
    if not all([username,password]):
        return render_template('admin/login.html',errmsg = '参数不足')
    #获取管理员用户数据  is_admin = True
    try:
        user = User.query.filter(User.mobile == username,User.is_admin==True).first()
    except Exception as e:
        current_app.logger.error(e)
        return render_template('admin/login.html',errmsg = '数据库操作失败')

    if not user: # 判断用户是否存在
        return render_template('admin/login.html',errmsg = '管理员不存在')

    #校验密码
    if not user.check_password(password):
        return render_template('admin/login.html',errmsg='账号/密码错误')

    #保存session数据 实现免密码登录
    session['user_id'] = user.id
    session['is_admin'] = True

    #校验成功,重定向到后台首页
    return  redirect(url_for('admin.index'))
"""
http://pkor83cv9.bkt.clouddn.com/Ft6TdYVQguA0FoKg0XS19n9GAJzB?imageView2/1/w/170/h/170

http://pkor83cv9.bkt.clouddn.com/FpqWjz9yjBvzIHhTvJvDrDZyuoBr

https://wpimg.wallstcn.com/7e2bd1e4-4152-47eb-9a6a-18d01f83c625.jpg?imageView2/1/w/170/h/170
"""

#后台退出登录
@admin_blu.route('/')
def logout():
    session.pop('user_id',None)
    session.pop('is_admin',None)
    #重定向到后台登录页面
    return redirect(url_for('admin.login'))


#后台首页
@admin_blu.route('/index')
@user_login_data
def index():
    return render_template('admin/index.html',user = g.user.to_dict())


#用户统计
@admin_blu.route('/user_count')
def user_count():

    #用户总数(除了管理员之外)
    try:
        total_count = User.query.filter(User.is_admin == False).count()
    except Exception as e:
        current_app.logger.error(e)
        total_count = 0


    #月新增人数  注册时间 >= 本月1号0点(默认是从0点开始)
    #获取当前时间的年和月
    t = time.localtime()
    #构建日期字符串  2019-01-01
    mon_date_str = '%d-%02d-01'%(t.tm_year,t.tm_mon)
    #转换为日期对象
    mon_date = datetime.strptime(mon_date_str,"%Y-%m-%d")
    try:
        mon_count = User.query.filter(User.is_admin == False,User.create_time >= mon_date).count()
    except Exception as e:
        current_app.logger.error(e)
        mon_count = 0


    #日新增人数  注册时间>=本月本日0点
    #构建日期字符串  2019-01-05
    day_date_str = "%d-%02d-%02d"%(t.tm_year,t.tm_mon,t.tm_mday)

    #转换为日期对象
    day_date = datetime.strptime(day_date_str,"%Y-%m-%d")
    try:
        day_count = User.query.filter(User.is_admin == False,User.create_time >= day_date).count()
    except Exception as e:
        current_app.logger.error(e)
        day_count = 0


    #曲线图
    #某日的注册人数  注册时间 >= 当日0点 ,<次日0点
    active_count = []
    active_time = []

    for i in range(0,30):
        begin_date = day_date - timedelta(days=i) #当日0点
        end_date = begin_date + timedelta(days=1) #次日0点

        try:
            one_day_count = User.query.filter(User.is_admin == False,User.create_time >= begin_date,User.create_time < end_date).count()

            active_count.append(one_day_count) #存放日期对应的注册人数

            #将日期对象转为日期字符串
            one_day_str = begin_date.strftime("%Y-%m-%d")
            active_time.append(one_day_str) #存放日期字符串

        except Exception as e:
            current_app.logger.error(e)
            one_day_count = 0

    #日期和注册量倒序
    active_time.reverse()
    active_count.reverse()

    data = {
        'total_count':total_count,
        'mon_count':mon_count,
        'day_count':day_count,
        'active_count':active_count,
        'active_time':active_time
    }

    return render_template('admin/user_count.html',data = data)



#用户列表
@admin_blu.route('/user_list')
def user_list():
    #获取参数
    p = request.args.get('p', 1)
    #校验参数
    try:
        p =int(p)
    except Exception as e:
        current_app.logger.error(e)
        return abort(403)

    #查询所有用户的数据  分页查
    try:
        pn = User.query.paginate(p,USER_COLLECTION_MAX_NEWS)
    except Exception as e:
        current_app.logger.error(e)
        return abort(500)

    data = {
        'user_list':[user.to_admin_dict()for user in pn.items],
        'total_page':pn.pages,
        'cur_page':pn.page
    }
    return render_template('admin/user_list.html',data=data)


#新闻审核
@admin_blu.route('/news_review')
def news_review():
    #获取参数
    p = request.args.get('p', 1)
    keyword = request.args.get('keyword')
    #校验参数
    try:
        p =int(p)
    except Exception as e:
        current_app.logger.error(e)
        return abort(403)

    #查询所有的新闻,分页处理,有搜索的按照搜索过滤
    filter_list = []   #此列表用来存放条件

    if keyword:
        filter_list.append(News.title.contains(keyword))

    try:
        pn = News.query.filter(*filter_list).order_by(News.status.asc()).paginate(p,USER_COLLECTION_MAX_NEWS)
    except Exception as e:
        current_app.logger.error(e)
        return abort(500)

    data = {
        'news_list': [news.to_review_dict() for news in pn.items],
        'total_page': pn.pages,
        'cur_page': pn.page
    }
    # 模板渲染
    return render_template('admin/news_review.html', data=data)


#审核详情
@admin_blu.route('/news_review_detail/<int:news_id>')
def news_review_detail(news_id):
    #根据新闻id查询新闻数据
    try:
        news = News.query.get(news_id)

    except Exception as e:
        current_app.logger.error(e)
        abort(500)

    #传入模板渲染
    return render_template('admin/news_review_detail.html', news= news.to_dict())


#提交审核结果
@admin_blu.route('/news_review_action',methods=["POST"])
def news_review_action():
    #获取参数
    news_id = request.json.get('news_id')
    action = request.json.get('action')
    reason = request.json.get('reason')
    #校验参数
    if not all([news_id,action]):
        return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])
    
    if action not in['accept','reject']:
        return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])
    
    try:
        news_id = int(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])
    #获取新闻数据
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno = RET.DBERR,errmsg = error_map[RET.DBERR])
    #根据action修改新闻的状态
    if action == 'accept':
        news.status = 0
    else:
        #不通过,要写原因
        if not reason:
            return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])
        news.reason = reason
        news.status = -1
    #返回json
    return jsonify(errno = RET.OK,errmsg = error_map[RET.OK])



#新闻编辑列表(同新闻审核逻辑一样)
@admin_blu.route('/news_edit')
def news_edit():
    #获取参数
    p = request.args.get('p', 1)
    keyword = request.args.get('keyword')
    #校验参数
    try:
        p =int(p)
    except Exception as e:
        current_app.logger.error(e)
        return abort(403)

    #查询所有的新闻,分页处理,有搜索的按照搜索过滤
    filter_list = []   #此列表用来存放条件

    if keyword:
        filter_list.append(News.title.contains(keyword))

    try:
        pn = News.query.filter(*filter_list).paginate(p,USER_COLLECTION_MAX_NEWS)
    except Exception as e:
        current_app.logger.error(e)
        return abort(500)

    data = {
        'news_list': [news.to_review_dict() for news in pn.items],
        'total_page': pn.pages,
        'cur_page': pn.page
    }
    # 模板渲染
    return render_template('admin/news_edit.html', data=data)


#编辑详情
@admin_blu.route('/news_edit_detail')
def news_edit_detail():
    #获取参数
    news_id = request.args.get('news_id')
    #校验参数
    try:
        news_id = int(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return abort(403)

    #根据新闻id查询新闻数据
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        abort(500)
    #查询所有分类
    try:
        categories = Category.query.filter(Category.id != 1).all()
    except Exception as e:
        current_app.logger.error(e)
        abort(500)

    #标识新闻当前的分类
    category_list = []
    for category in categories:
        category_dict = category.to_dict()
        is_selected = False
        if category.id == news.category_id:
            is_selected = True

        category_dict['is_selected'] = is_selected
        category_list.append(category_dict)
    #传入模板渲染
    return render_template('admin/news_edit_detail.html', news= news.to_dict(),category_list=category_list)


#提交编辑
@admin_blu.route('/news_edit_detail',methods = ["POST"])
def news_edit_detail_post():#一个路由可以分成多个视图函数来完成不同请求方式的处理,注意视图函数的标记不能相同
    #获取参数
    news_id = request.form.get('news_id')
    title = request.form.get('title')
    category_id = request.form.get('category_id')
    digest = request.form.get('digest')
    content = request.form.get('content')
    index_image = request.files.get('index_image')
    #校验参数
    if not all([news_id,title,category_id,digest,content]):
        return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])
    try:
        news_id = int(news_id)
        category_id = int(category_id)
    except Exception as e:
        current_app.logger(e)
        return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])

    #查询新闻数据
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno = RET.DBERR,errmsg = error_map[RET.DBERR])

    #修改新闻数据
    news.title = title
    news.category_id = category_id
    news.digest = digest
    news.content = content
    if index_image:
        try:
            #读取内容
            img_bytes = index_image.read()
            #上传到七牛云
            file_name = file_upload(img_bytes)
            news.index_image_url = QINIU_DOMIN_PREFIX + file_name
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno = RET.THIRDERR,errmsg = error_map[RET.THIRDERR])

    #json返回
    return jsonify(errno = RET.OK,errmsg = error_map[RET.OK])


#新闻分类
@admin_blu.route('/news_type',methods=['GET',"POST"])
def news_type():
    #GET展示页面
    if request.method == 'GET':
        #查询所有分类数据
        try:
            categories = Category.query.filter(Category.id != 1).all()
        except Exception as e:
            current_app.logger.error(e)
            return abort(500)
        #传入模板渲染
        return render_template('admin/news_type.html',categories = categories)
    
    #POST请求
    id = request.json.get('id')
    name = request.json.get('name')
    if not name:
        return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])
    if  id:  #id 存在.可以修改分类
        try:
            id = int(id)
            category = Category.query.get(id)
            category.name = name
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])
        
    else: #新增分类
        new_category = Category(name=name)
        db.session.add(new_category)
        
    return jsonify(errno = RET.OK,errmsg = error_map[RET.OK])
        
            
