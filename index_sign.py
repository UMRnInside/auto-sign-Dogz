# -*- coding: utf-8 -*-
import requests
import sys, os
import json
import yaml
import login
from datetime import datetime, timedelta, timezone
import sendEmail

############配置############
# Cookies = {
#     'acw_tc': '',
#     'MOD_AUTH_CAS': '',
# }
# CpdailyInfo = ''
# sessionToken = ''
##########自动配置###########
try:
    loginSession = os.path.join(sys.path[0], 'config', 'loginSession.yml')
    with open(loginSession, 'r', encoding='utf-8') as f:
        file_data = f.read()
        config_read = yaml.load(file_data, Loader=yaml.FullLoader)
        Cookies = {
            'acw_tc': config_read['sessionCookies']['acw_tc'],
            'MOD_AUTH_CAS': config_read['sessionCookies']['MOD_AUTH_CAS'],
        }
        CpdailyInfo = config_read['CpdailyInfo']
        if CpdailyInfo == 'dynamic':
            CpdailyInfo = login.CpdailyInfo

        sessionToken = config_read['sessionToken']
except IOError:
    print('读取登陆配置文件出错！请查看是否存在配置文件，或重新登陆。\n')
    print(IOError)
############配置############

# 全局

host = login.host
session = requests.session()
session.cookies = requests.utils.cookiejar_from_dict(Cookies)


# 读取yml配置
def getYmlConfig(yaml_file='config/config_sign.yml'):
    file = open(yaml_file, 'r', encoding="utf-8")
    file_data = file.read()
    file.close()
    config = yaml.load(file_data, Loader=yaml.FullLoader)
    return dict(config)

yaml_file = os.path.join(sys.path[0], 'config', 'config_sign.yml')
config = getYmlConfig(yaml_file)
user = config['user']
email_yml = config['email']


# 获取当前utc时间，并格式化为北京时间
def getTimeStr():
    utc_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
    bj_dt = utc_dt.astimezone(timezone(timedelta(hours=8)))
    return bj_dt.strftime("%Y-%m-%d %H:%M:%S")


# 输出调试信息，并及时刷新缓冲区
def log(content):
    print(getTimeStr() + ' ' + str(content))
    sys.stdout.flush()


# 获取最新未签到任务
def getUnSignedTasks():
    headers = {
        'Host': host,
        'Connection': 'keep-alive',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://' + host,
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 4.4.4; PCRT00 Build/KTU84P) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/33.0.0.0 Safari/537.36 cpdaily/8.0.8 wisedu/8.0.8',
        'Content-Type': 'application/json',
        'Accept-Encoding': 'gzip,deflate',
        'Accept-Language': 'zh-CN,en-US;q=0.8',
    }
    params = {}
    #url = 'https://{host}/wec-counselor-sign-apps/stu/sign/queryDailySginTasks'.format(host=host)
    url = 'https://{host}/wec-counselor-sign-apps/stu/sign/getStuSignInfosInOneDay'.format(host=host)
    res = session.post(url=url, headers=headers, data=json.dumps(params))
    # log(res.json())
    unSignedTasks = res.json()['datas']['unSignedTasks']
    signedTasks = res.json()['datas']['signedTasks']
    print(unSignedTasks)
    print(json.dumps(res.json(), indent=4, ensure_ascii=False))
    if len(unSignedTasks) < 1:
        log('当前没有未签到任务')
        exit(-1)
    latestTask = unSignedTasks[0]
    return {
        'signInstanceWid': latestTask['signInstanceWid'],
        'signWid': latestTask['signWid']
    }


# 获取签到任务详情
def getDetailTask(params):
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
        'content-type': 'application/json',
        'Accept-Encoding': 'gzip,deflate',
        'Accept-Language': 'zh-CN,en-US;q=0.8',
        'Content-Type': 'application/json;charset=UTF-8'
    }
    res = session.post(
        url='https://{host}/wec-counselor-sign-apps/stu/sign/detailSignInstance'.format(host=host),
        headers=headers, data=json.dumps(params))
    print(json.dumps(res.json(), indent=4, ensure_ascii=False))
    data = res.json()['datas']
    return data


# 填充表单
def fillForm(task):
    form = {}
    form['signPhotoUrl'] = ''
    if task['isNeedExtra'] == 1:
        extraFields = task['extraField']
        defaults = config['cpdaily']['defaults']
        extraFieldItemValues = []
        for i in range(0, len(extraFields)):
            default = defaults[i]['default']
            extraField = extraFields[i]
            if default['title'] != extraField['title']:
                log('第%d个默认配置项错误，请检查' % (i + 1))
                exit(-1)
            extraFieldItems = extraField['extraFieldItems']
            for extraFieldItem in extraFieldItems:
                if extraFieldItem['content'] == default['value']:
                    extraFieldItemValue = {'extraFieldItemValue': default['value'],
                                           'extraFieldItemWid': extraFieldItem['wid']}
                    extraFieldItemValues.append(extraFieldItemValue)
        # log(extraFieldItemValues)
        # 处理带附加选项的签到
        form['extraFieldItems'] = extraFieldItemValues
    # form['signInstanceWid'] = params['signInstanceWid']
    form['signInstanceWid'] = task['signInstanceWid']
    form['longitude'] = user['lon']
    form['latitude'] = user['lat']
    form['isMalposition'] = task['isMalposition']
    form['abnormalReason'] = user['abnormalReason']
    form['position'] = user['address']
    print(form)
    return form


# 提交签到任务
def submitForm(form):
    headers = {
        # 'tenantId': '1019318364515869',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 4.4.4; OPPO R11 Plus Build/KTU84P) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/33.0.0.0 Safari/537.36 okhttp/3.12.4',
        'CpdailyStandAlone': '0',
        'extension': '1',
        'Cpdaily-Extension': CpdailyInfo,
        'Content-Type': 'application/json; charset=utf-8',
        'Accept-Encoding': 'gzip',
        # 'Host': 'swu.cpdaily.com',
        'Connection': 'Keep-Alive'
    }
    res = session.post(url='https://{host}/wec-counselor-sign-apps/stu/sign/submitSign'.format(host=host),
                       headers=headers, data=json.dumps(form))
    message = res.json()['message']
    if message == 'SUCCESS':
        log('自动签到成功')
        sendMessage('自动签到成功', user['email'])
    else:
        log('自动签到失败，原因是：' + message)
        sendMessage('自动签到失败，原因是：' + message, user['email'])
        exit(-1)


# 发送邮件通知
def sendMessage(msg, email):
    send = email
    isAuthor = email_yml['isAuthor']
    if send != '':
        #使用原作者邮箱服务
        if int(isAuthor) == 1:
            log('正在发送邮件通知。。。')
            res = requests.post(url='http://www.zimo.wiki:8080/mail-sender/sendMail',
                                data={'title': '今日校园自动签到结果通知', 'content': msg, 'to': send})
            code = res.json()['code']
            if code == 0:
                log('发送邮件通知成功。。。')
            else:
                log('发送邮件通知失败。。。')
                log(res.json())
        else: #使用自己邮箱发送结果
            log('正在发送邮件通知。。。')
            code = sendEmail.sendEmail(msg, send)
            if code == 0:
                log('发送邮件通知成功。。。')
            else:
                log('发送邮件通知失败。。。')
                log(code)



def main():
    data = {
        'sessionToken': sessionToken
    }
    login.getModAuthCas(data)
    params = getUnSignedTasks()
    # log(params)
    task = getDetailTask(params)
    # log(task)
    form = fillForm(task)
    # log(form)
    submitForm(form)


# 提供给腾讯云函数调用的启动函数
def main_handler(event, context):
    try:
        main()
        return 'success'
    except:
        raise
        return 'fail'


if __name__ == '__main__':
    print(main_handler({}, {}))
