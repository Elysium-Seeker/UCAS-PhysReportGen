import requests
import json
import sys

# 用户提供的配置
API_URL = "https://api.laozhang.ai/v1/chat/completions"
API_KEY = "sk-3uIOrN1iib91gIXr259fA70769C740D7B3Cf6aE79496E733"
MODEL = "gemini-3-flash-preview"  # 用户指定的模型

def test_api():
    print(f"正在测试 API: {API_URL}")
    print(f"Key: {API_KEY[:8]}...{API_KEY[-4:]}")
    print(f"Model: {MODEL}")
    print("-" * 50)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": "你好，请回复'API测试成功'。"}
        ],
        "temperature": 0.7
    }

    try:
        print("发送请求中...")
        response = requests.post(API_URL, headers=headers, json=data, timeout=30)
        
        print(f"状态码: {response.status_code}")
        
        with open('test_result.txt', 'w', encoding='utf-8') as f:
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                print("\n✅ API 连接成功！")
                print(f"回复内容: {content}")
                f.write(f"SUCCESS\n{content}")
                return True
            else:
                print("\n❌ API 请求失败")
                print(f"响应内容: {response.text}")
                f.write(f"FAILURE\n{response.text}")
                return False
            
    except Exception as e:
        print(f"\n❌ 发生异常: {str(e)}")
        with open('test_result.txt', 'w', encoding='utf-8') as f:
            f.write(f"ERROR\n{str(e)}")
        return False

if __name__ == "__main__":
    test_api()
