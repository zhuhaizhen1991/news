import datetime
import random
from datetime import timedelta
from flask import Flask, session
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from redis import Redis
from config import ProductionConfig
from info import create_app

app = create_app('dev')

#创建管理器
mgr = Manager(app)
#使用管理器生成迁移命令
mgr.add_command('mc',MigrateCommand)

#添加管理员账号
#  @mgr.command   将无参函数变为命令
@mgr.option('-u',dest='username') #python main.py create_superuser -u admin -p 123456
@mgr.option('-p',dest='password')  #将有参函数变为命令
def create_superuser(username,password):
    if not all([username,password]):
        app.logger.error('添加管理员失败:参数不足')
        return

    from info.utils.models import User
    from info import create_app, db
    #添加管理员用户  is_admin = True
    user = User()
    user.mobile = username
    user.password = password
    user.nick_name = username
    user.is_admin = True

    db.session.add(user)
    try:
        db.session.commit()
    except Exception as e:
        app.logger.error('添加管理员失败:%s'% e)
        db.session.rollback()
        return

    app.logger.info('添加管理员成功')


#添加测试数据
@mgr.command
def add_test_users():
    """添加测试数据"""

    from info.utils.models import User
    from info import db
    users = []
    now = datetime.datetime.now()
    for num in range(0,10000):
        try:

            user = User()
            user.nick_name = "%011d" % num
            user.mobile = "%011d" % num
            user.password_hash = "pbkdf2:sha256:50000$SgZPAbEj$a253b9220b7a916e03bf27119d401c48ff4a1c81d7e00644e0aaf6f3a8c55829"
            user.create_time = now - datetime.timedelta(seconds=random.randint(0, 2678400))
            users.append(user)
            print(user.mobile)
        except Exception as e:
            print(e)
        db.session.add_all(users)
        db.session.commit()
        print('OK')

if __name__ == '__main__':
    mgr.run()