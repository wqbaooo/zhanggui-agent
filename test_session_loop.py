#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试新版 Session 引擎的闭环能力。"""

from core.session import Session
from models.state import ProfileField

def main():
    agent = Session()
    
    # 模拟用户输入
    user_input = "我想在新余恒太城五楼开一个餐饮店，选什么品类比较好？商业环境如何？我的预算10万左右。"
    
    # 【调试用】手动注入画像，确保 Agent 拿到关键信息
    agent.agent_state.merge_profile({
        "城市": ProfileField(value="新余"),
        "商圈": ProfileField(value="恒太城五楼"),
        "预算": ProfileField(value="10万"),
        "品类": ProfileField(value="餐饮")
    }, turn=0)
    
    print(f"🤖 开店顾问: 正在分析 '{user_input}' ...\n")
    
    # 运行完整状态机闭环
    response = agent.process_turn(user_input)
    
    # 打印最终回复
    print(response.response_text)
    
    # 打印审计信息
    audit_info = agent.audit_sources()
    if audit_info:
        print("\n## 知识源状态")
        print(f"- RAG 索引总量：{audit_info.get('chunks', 0)}")
        print(f"- 视频已转写：{audit_info.get('by_status', {}).get('usable', 0)}")

if __name__ == "__main__":
    main()
