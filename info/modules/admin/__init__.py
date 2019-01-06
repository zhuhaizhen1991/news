#创建蓝图对象
from flask import Blueprint

admin_blu = Blueprint('admin', __name__,url_prefix='/admin')

#添加蓝图请求钩子,只会对蓝图注册的路由进行监听
@admin_blu.before_request
def check_superuser():
    is_admin = session.get('is_admin')
    if not is_admin and not request.url.endswith(url_for('admin.login')):#管理员未登录 并且 不是访问的后台登录页面,跳转到前台首页
        return redirect(url_for('home.index'))


#将蓝图与项目之间建立关联
from .views import *