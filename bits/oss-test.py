# -*- coding: utf-8 -*-
import oss2

# 从环境变量中获取访问凭证。运行本代码示例之前，请确保已设置环境变量OSS_ACCESS_KEY_ID和OSS_ACCESS_KEY_SECRET。
# 填写RAM用户的Access Key ID和Access Key Secret
access_key_id = ''
access_key_secret = ''

# 使用RAM用户的访问密钥配置访问凭证，请注意，此处使用AuthV4表示使用V4签名。
auth = oss2.AuthV4(access_key_id, access_key_secret)

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
result = bucket.put_object_from_file(objectName, local_file_path)
print(f'status code: {result.status},' # 200为正常
          f' request id: {result.request_id},'
          f' content crc: {result.crc},'
          f' etag: {result.etag},'
          f' headers: {result.headers},'
          f' delete_marker: {result.delete_marker}'
    )


url = bucket.sign_url('GET', objectName, 600, slash_safe=True)
print('预签名URL的地址为：', url)