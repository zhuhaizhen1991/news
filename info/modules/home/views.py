
from info.modules.home import home_blu
from flask import current_app, render_template, session, request, jsonify, abort

from info.utils.constants import HOME_PAGE_MAX_NEWS
from info.utils.models import User, News, Category

#使用蓝图对象注册路由
from info.utils.response_code import RET, error_map


@home_blu.route('/')
def index():
    #判断用户是否已经登录
    user_id = session.get('user_id')
    user = None
    if user_id: # 已登录
        try:
            user = User.query.get(user_id)

        except Exception as e:
            current_app.logger.error(e)

    # 查询点击量前10的新闻
    rank_list = []
    try:
        rank_list = News.query.order_by(News.clicks.desc()).limit(10).all()
    except BaseException as e:
        current_app.lgger.error(e)

    rank_list = [news.to_basic_dict() for news in rank_list]

    #查询所有的分类数据
    try:
        categories = Category.query.all()
    except BaseException as e:
        current_app.logger.error(e)
        return abort(500)

    user = user.to_dict() if user else None
    #将登录数据,排行数据,分类数据,传入模板渲染
    return render_template('news/index.html', user=user, rank_list=rank_list, categories = categories)


#设置网站图标(浏览器会自动向网站发起/favicon.ico请求,后端只需要实现该路由,并返回图片即可)
@home_blu.route('/favicon.ico')
def favico():
    # flask中封装了语法send_static_file
    #可以获取静态文件的内容,封装为响应对象,并根据内容设置content-type
    response = current_app.send_static_file('news/favicon.ico') #相对路径基于static文件夹而来
    return response


#获取新闻列表
@home_blu.route('/get_news_list')
def get_news_list():
    #获取参数
    cid = request.args.get('cid')
    cur_page = request.args.get('cur_page')
    per_count = request.args.get('per_count',HOME_PAGE_MAX_NEWS)
    #校验参数
    if not all([cid,cur_page,per_count]):
        return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])

    try:
        cid = int(cid)
        cur_page = int(cur_page)
        per_count = int(per_count)
    except Exception as e:
        current_app.lgger.error(e)
        return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])

    #新闻只显示审核通过的
    filter_list = [News.status==0]
    if cid != 1: # 不是'最新'
        filter_list.append(News.category_id == cid)

    #根据分类,页码查询新闻数据,根据新闻发布时间倒序
    try:
        pn = News.query.filter(*filter_list).order_by(News.create_time.desc()).paginate(cur_page,per_count)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno = RET.DBERR,errmsg = error_map[RET.DBERR])


    # 根据分类,页码查询新闻数据,根据新闻发布时间倒序
    #第二种方式:
    # if cid != 1:
    #     # 不是'最新'这个分类,按对应分类的新闻排序
    #     try:
    #         pn = News.query.filter_by(category_id=cid).order_by(News.create_time.desc()).paginate(cur_page, per_count)
    #     except Exception as e:
    #         current_app.logger.error(e)
    #         return jsonify(errno=RET.DBERR, errmsg=error_map[RET.DBERR])
    #
    # else:
    #     # 是'最新'这个分类,按所有新闻排序
    #     try:
    #         pn = News.query.order_by(News.create_time.desc()).paginate(cur_page, per_count)
    #     except Exception as e:
    #         current_app.logger.error(e)
    #         return jsonify(errno=RET.DBERR, errmsg=error_map[RET.DBERR])


    #数据包装成json返回
    data = {
        'news_list':[news.to_basic_dict() for news in pn.items],
        'total_page':pn.pages
    }
    return jsonify(errno = RET.OK,errmsg = error_map[RET.OK],data=data)