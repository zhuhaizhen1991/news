#创建蓝图对象
from flask import Blueprint

home_blu = Blueprint('home', __name__)

#将蓝图与项目之间建立关联
from .views import *