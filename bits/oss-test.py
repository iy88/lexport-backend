# -*- coding: utf-8 -*-
import oss2
from oss2.credentials import EnvironmentVariableCredentialsProvider

# 从环境变量中获取访问凭证。运行本代码示例之前，请确保已设置环境变量OSS_ACCESS_KEY_ID和OSS_ACCESS_KEY_SECRET。
auth = oss2.ProviderAuthV4(EnvironmentVariableCredentialsProvider())

# 填写Bucket所在地域对应的Endpoint。以华东1（杭州）为例，Endpoint填写为https://oss-cn-hangzhou.aliyuncs.com。
endpoint = "https://oss-cn-beijing.aliyuncs.com"

# 填写Endpoint对应的Region信息，例如cn-hangzhou。注意，v4签名下，必须填写该参数
region = "cn-beijing"
# 填写Bucket名称，例如examplebucket。
bucketName = "lexport-tmp-file"
# 创建Bucket实例，指定存储空间的名称和Region信息。
bucket = oss2.Bucket(auth, endpoint, bucketName, region=region)

# 本地文件的完整路径
local_file_path = '/Users/iy88/Code/Github/LexPort/尼日利亚相关法规/13《尼日利亚个人所得税法》PITA-2004.pdf'

# 填写Object完整路径，完整路径中不能包含Bucket名称。例如exampleobject.txt。
objectName = '13《尼日利亚个人所得税法》PITA-2004.pdf'

# 使用put_object_from_file方法将本地文件上传至OSS
put_res = bucket.put_object_from_file(objectName, local_file_path)
print(put_res)

url = bucket.sign_url('GET', objectName, 600, slash_safe=True)
print('预签名URL的地址为：', url)