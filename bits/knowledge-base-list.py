# -*- coding: utf-8 -*-
# This file is auto-generated, don't edit it. Thanks.
import os
import sys
import json

from typing import List

from alibabacloud_bailian20231229.client import Client as bailian20231229Client
from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_bailian20231229 import models as bailian_20231229_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_credentials.models import Config as CredentialConfig


class Sample:
    def __init__(self):
        pass

    @staticmethod
    def create_client() -> bailian20231229Client:
        """
        使用凭据初始化账号Client
        @return: Client
        @throws Exception
        """
        # 工程代码建议使用更安全的无AK方式，凭据配置方式请参见：https://help.aliyun.com/document_detail/378659.html。
        credentialsConfig = CredentialConfig(
            type='access_key',
            # 必填参数，此处以从环境变量中获取AccessKey ID为例
            access_key_id="",
            # 必填参数，此处以从环境变量中获取AccessKey Secret为例
            access_key_secret=""
        )
        credential = CredentialClient(credentialsConfig)
        config = open_api_models.Config(
            credential=credential
        )
        # Endpoint 请参考 https://api.aliyun.com/product/bailian
        config.endpoint = f'bailian.cn-beijing.aliyuncs.com'
        return bailian20231229Client(config)

    @staticmethod
    def main(
        args: List[str],
    ) -> None:
        client = Sample.create_client()
        list_indices_request = bailian_20231229_models.ListIndicesRequest()
        runtime = util_models.RuntimeOptions()
        headers = {}
        try:
            resp = client.list_indices_with_options('ws-j9b8mc0mky7cknrz', list_indices_request, headers, runtime)
            print(json.dumps(resp, default=str, indent=2))
        except Exception as error:
            # 此处仅做打印展示，请谨慎对待异常处理，在工程项目中切勿直接忽略异常。
            # 错误 message
            print(error.message)
            # 诊断地址
            print(error.data.get("Recommend"))

    @staticmethod
    async def main_async(
        args: List[str],
    ) -> None:
        client = Sample.create_client()
        list_indices_request = bailian_20231229_models.ListIndicesRequest()
        runtime = util_models.RuntimeOptions()
        headers = {}
        try:
            resp = await client.list_indices_with_options_async('ws-j9b8mc0mky7cknrz', list_indices_request, headers, runtime)
            print(json.dumps(resp, default=str, indent=2))
        except Exception as error:
            # 此处仅做打印展示，请谨慎对待异常处理，在工程项目中切勿直接忽略异常。
            # 错误 message
            print(error.message)
            # 诊断地址
            print(error.data.get("Recommend"))


if __name__ == '__main__':
    Sample.main(sys.argv[1:])