from flask import g, redirect, url_for, render_template, abort, request, jsonify, current_app

from info import db
from info.modules.user import user_blu
from info.utils.common import user_login_data, file_upload

#个人中心
from info.utils.constants import USER_COLLECTION_MAX_NEWS, QINIU_DOMIN_PREFIX
from info.utils.models import UserCollection, Category, News
from info.utils.response_code import RET, error_map


@user_blu.route('/user_info')
@user_login_data
def user_info():
    user = g.user
    if not user:  # 用户未登录,重定向到前台首页
        return  redirect(url_for('home.index'))

    return render_template('news/user.html', user = user.to_dict())


#基本资料
@user_blu.route('/base_info',methods = ["GET","POST"])
@user_login_data
def base_info():
    user = g.user
    if not user:# 未登录
        return abort(403)

    if request.method == 'GET':# GET 展示页面
        return render_template('news/user_base_info.html', user=user.to_dict())

    #POST 提交资料

    #获取参数
    signature = request.json.get('signature')
    nick_name = request.json.get('nick_name')
    gender = request.json.get('gender')
    #校验参数
    if not all([signature,nick_name,gender]):
        return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])

    if gender not in['MAN',"WOMAN"]:
        return jsonify(errno=RET.PARAMERR, errmsg=error_map[RET.PARAMERR])

    #修改用户数据
    user.nick_name = nick_name
    user.signature = signature
    user.gender = gender

    #json返回
    return jsonify(errno = RET.OK,errmsg = error_map[RET.OK])


#头像设置
@user_blu.route('/pic_info',methods = ['GET','POST'])
@user_login_data
def pic_info():
    user = g.user
    if not user:
        return abort(403)

    if request.method == 'GET': # GET展示页面
        return render_template('news/user_pic_info.html', user = user.to_dict())

    #post提交资料

    #获取参数
    avatar_file = request.files.get('avatar')

    #获取文件数据
    try:
        file_bytes = avatar_file.read()
        # print(file_bytes)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])
        
    #上传文件到七牛云服务器 一般会将文件单独管理起来 业务服务器 文件服务器
    try:
        file_name = file_upload(file_bytes)
    except Exception as e:
        current_app.lgger.error(e)
        return jsonify(errno = RET.THIRDERR,errmsg = error_map[RET.THIRDERR])
    #修改头像链接
    user.avatar_url = file_name
    print(file_name)
    #json返回 必须返回头像链接
    return  jsonify(errno = RET.OK,errmsg = error_map[RET.OK],data = user.to_dict())


#设置密码
@user_blu.route('/pass_info',methods = ['GET','POST'])
@user_login_data
def pass_info():
    user = g.user
    if not user : # 未登录
        return abort(403)

    if request.method == 'GET':# GET展示页面
        #直接返回静态页面
        return current_app.send_static_file('info/static/news/html/user_pass_info.html')

    #POST 提交资料
    #获取参数
    old_password = request.json.get('old_password')
    new_password = request.json.get('new_password')
    #校验密码
    if not all([old_password,new_password]):
        return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])

    #校验旧密码
    if not user.check_password(old_password):
        return jsonify(errno = RET.PWDERR,errmsg = error_map[RET.PWDERR])

    #修改新密码
    user.password = new_password
    #json返回
    return jsonify(errno = RET.OK,errmsg = error_map[RET.OK])


#显示收藏
@user_blu.route('/collection')
@user_login_data
def collection():
    user = g.user
    if not user: # 未登录
        return abort(403)

    #获取参数
    p = request.args.get('p', 1)
    #校验参数
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        return abort(403)

    #查询当前用户收藏的新闻  分页查询  收藏时间倒序
    try:
        pn = user.collection_news.order_by(UserCollection.create_time.desc()).paginate(p,USER_COLLECTION_MAX_NEWS)
    except Exception as e:
        current_app.logger.error(e)
        return abort(500)

    data = {
        'news_list':[news.to_dict() for news in pn.items],
        'total_page':pn.pages,
        'cur_page':pn.page
    }

    #将数据传入模板渲染
    return  render_template('news/user_collection.html', data = data)


#新闻发布
@user_blu.route('/news_release',methods=['GET','POST'])
@user_login_data
def news_release():
    user = g.user
    if not user:
        return abort(403)

    if request.method == 'GET': # GET 展示页面
        #查询分类数据
        try:
            categories = Category.query.filter(Category.id != 1).all()
        except Exception as e:
            current_app.logger.error(e)
            return  abort(500)

        #将分类数据传入模板
        return render_template('news/user_news_release.html', categories=categories)

    #POST提交资料
    #获取参数
    title = request.form.get('title')
    category_id = request.form.get('category_id')
    digest = request.form.get('digest')
    content = request.form.get('content')
    img_file = request.files.get('index_image')
    #校验参数
    if not all([title,category_id,digest,content,img_file]):
        return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])

    try:
        category_id = int(category_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])

    #生成一条新闻数据
    news =  News()
    news.title = title
    news.category_id = category_id
    news.digest = digest
    news.content = content

    try:
        img_bytes = img_file.read()
        file_name = file_upload(img_bytes) # 上传图片
        news.index_image_url = QINIU_DOMIN_PREFIX + file_name
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno = RET.THIRDERR,errmsg = error_map[RET.THIRDERR])
    #设置其他数据
    news.source = '个人发布'
    news.user_id = user.id  #作者id
    news.status = 1 #待审核状态
    #添加到数据库
    db.session.add(news)
    #json返回结果
    return jsonify(errno = RET.OK,errmsg = error_map[RET.OK])

#我的发布新闻列表
@user_blu.route('/news_list')
@user_login_data
def news_list():
    user = g.user
    if not user:
        return abort(403)

    #获取参数
    p = request.args.get('p', 1)
    #校验参数
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        return abort(403)

    # 查询当前用户发布的新闻  分页查询  发布时间倒序
    try:
        pn = user.news_list.order_by(News.create_time.desc()).paginate(p, USER_COLLECTION_MAX_NEWS)
    except Exception as e:
        current_app.logger.error(e)
        return abort(500)

    data = {
        'news_list': [news.to_review_dict() for news in pn.items],
        'total_page': pn.pages,
        'cur_page': pn.page
    }

    # 将数据传入模板渲染
    return render_template('news/user_news_list.html', data=data)

#我的关注
@user_blu.route('/user_follow')
@user_login_data
def user_follow():
    user = g.user
    if not user:  # 用户未登录
        return abort(403)

    #获取参数
    p = request.args.get('p',1)
    #校验参数
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        return abort(403)

    #查询当前用户关注的作者  分页查询
    try:
        pn = user.followed.paginate(p, USER_COLLECTION_MAX_NEWS)
    except Exception as e:
        current_app.logger.error(e)
        return abort(500)

    #数据传入模板渲染
    data={
        'author_list':[user.to_dict() for user in pn.items],
        'total_page':pn.pages,
        'cur_page':pn.page

    }
    return render_template('news/user_follow.html', data = data)












