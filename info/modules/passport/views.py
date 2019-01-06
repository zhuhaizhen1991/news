from info import rs, db
import random
import re
from datetime import datetime

from flask import request, abort, current_app, make_response, Response, jsonify, session

from info.utils.constants import IMAGE_CODE_REDIS_EXPIRES, SMS_CODE_REDIS_EXPIRES
from info.libs.captcha.pic_captcha import captcha
from info.utils.models import User
from info.modules.passport import passport_blu

from info.utils.response_code import RET, error_map

#获取图片验证码
@passport_blu.route('/get_img_code')
def get_img_code():
    #获取参数
    img_code_id  = request.args.get('img_code_id')
    #校验参数
    if not img_code_id:
        return abort(403) #403表示拒绝访问

    #生成图片验证码(图片+文字)
    img_name,img_text,img_bytes = captcha.generate_captcha()

    #保存验证码文字和图片key   redis方便设置过期时间,性能也好,键值关系满足需求
    try:
        rs.set('img_code_id'+img_code_id,img_text,ex=IMAGE_CODE_REDIS_EXPIRES)
    except Exception as e:
        current_app.logger.error(e) #记录错误信息
        return abort(500)

    #返回图片 自定义响应对象
    response = make_response(img_bytes) #type:Response
    # 设置响应头
    response.content_type = 'image/jpeg'
    return response

#获取短信验证码
@passport_blu.route('/get_sms_code',methods = ['POST'])
def get_sms_code():
    #获取参数
    img_code_id = request.json.get('img_code_id')

    img_code = request.json.get('img_code')

    mobile = request.json.get('mobile')

    #校验参数
    if not all([img_code_id,img_code,mobile]):
        return jsonify(error = RET.PARAMERR,errmsg=error_map[RET.PARAMERR])
    #根据图片key取出验证码文字
    try:

        real_img_code = rs.get('img_code_id'+img_code_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(error = RET.DBERR,errmsg=error_map[RET.DBERR])

    #校验图片验证码(文字)
    if real_img_code != img_code.upper():
        return jsonify(error = RET.PARAMERR,errmsg=error_map[RET.PARAMERR])

    #判断用户是否存在
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno = RET.DBERR,errmsg = error_map[RET.DBERR])

    if user:
        return jsonify(errno = RET.DATAEXIST,errmsg = error_map[RET.DATAEXIST])

    #生成随机短信验证码
    rand_num = '%04d'% random.randint(0,9999)

    #发送短信
    # response_code = CCP().send_template_sms(mobile, [rand_num, 5], 1)
    # if response_code != 0:  # 发送失败
    #     return  jsonify(errno = RET.THIRDERR,errmsg = error_map[RET.THIRDERR])


    #保存短信验证码  redis 设置过期时间 key:手机号 value:短信验证码
    try:
        rs.set('sms_code_id_'+mobile,rand_num,ex = SMS_CODE_REDIS_EXPIRES)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno = RET.DBERR,errmsg = error_map[RET.DBERR])

    current_app.logger.info('短信验证码为:%s'%rand_num)

    #json返回发送结果
    return jsonify(error=RET.OK,errmsg=error_map[RET.OK])



#用户注册
@passport_blu.route('/register',methods=['POST'])
def register():
    #获取参数
    sms_code = request.json.get('sms_code')
    mobile = request.json.get('mobile')
    password = request.json.get('password')

    #校验参数
    if not all([sms_code,mobile,password]):
        return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])
    if not re.match(r'1[345678]\d{9}$',mobile):#手机号码校验
        return jsonify(errno=RET.PARAMERR, errmsg=error_map[RET.PARAMERR])

    #校验短信验证码(根据手机号取出短信验证码)
    try:
        real_sms_code = rs.get('sms_code_id_' + mobile)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno = RET.DBERR,errmsg = error_map[RET.DBERR])

    if real_sms_code != sms_code:
        return jsonify(errno=RET.PARAMERR, errmsg=error_map[RET.PARAMERR])

    #记录用户数据
    user = User()
    user.mobile = mobile
    user.nick_name = mobile
    # user.password_hash = password
    #使用计算型属性封装密码加密
    user.password = password

    db.session.add(user)

    try:
        db.session.commit()
    except Exception as e:
        current_app.lgger.error(e)
        db.session.rollback()
        return jsonify(errno = RET.DBERR,errmsg = error_map[RET.DBERR])

    #使用session记录用户登录状态 记录主键就可以查询其他的数据
    session['user.id'] = user.id
    #json返回结果
    return jsonify(errno = RET.OK,errmsg = error_map[RET.OK])


#用户登录
@passport_blu.route('/login',methods=['POST'])
def login():
    #获取参数
    mobile = request.json.get('mobile')
    password = request.json.get('password')
    #校验参数
    if not all([mobile,password]):
        return jsonify(errno = RET.PARAMERR,errmsg = error_map[RET.PARAMERR])

    #取出用户数据
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno = RET.DBERR,errmsg = error_map[RET.DBERR])

    #判断用户是否存在
    if not user:#用户不存在
        return jsonify(errno = RET.USERERR,errmsg = error_map[RET.USERERR])

    #校验密码
    if not user.check_password(password):
        return  jsonify(errno = RET.PWDERR,errmsg = error_map[RET.PWDERR])

    #使用session记录用户的登录状态,记录主键就可以查询出其他的数据
    session['user_id'] = user.id
    # 记录最后登录时间 使用sqlalchemy自动提交机制
    user.last_login = datetime.now()

    #json返回数据
    return jsonify(errno = RET.OK,errmsg = error_map[RET.OK])


#退出登录
@passport_blu.route('/logout')
def logout():
    #删除session中的user_id
    session.pop('user_id',None)
    session.pop('is_admin',None)
    return jsonify(errno = RET.OK,errmsg = error_map[RET.OK])










