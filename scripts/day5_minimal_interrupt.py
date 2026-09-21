"""Day 5：用最小图观察 interrupt、checkpoint 和 resume。"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class ClarificationState(TypedDict, total=False):
    """最小中断图在节点之间传递的业务数据。"""

    question: str
    answer: str


def ask_node(state: ClarificationState) -> dict[str, str]:
    """暂停图；恢复值会成为 interrupt 的返回值。"""
    print("开始进入ask_node")
    answer = interrupt(
        {
            "kind": "evidence_clarification",
            "question": state["question"],
        }
    )
    print("interrupt已经获得恢复值")
    return {"answer": answer}


builder = StateGraph(ClarificationState)
builder.add_node("ask", ask_node)
builder.add_edge(START, "ask")
builder.add_edge("ask", END)

graph = builder.compile(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "day5-minimal-demo"}}

first_result = graph.invoke(
    {"question": "请描述一段你实际使用 LangGraph 的经历。"},
    config=config,
)
print("首次运行：图已暂停，等待用户补充证据。")


assert "__interrupt__" in first_result
interrupt_payload = first_result["__interrupt__"][0].value
assert interrupt_payload == {
    "kind": "evidence_clarification",
    "question": "请描述一段你实际使用 LangGraph 的经历。",
}
assert "answer" not in first_result

user_answer = "我实现了一个根据证据是否充分进行条件路由的 LangGraph。"
final_state = graph.invoke(
    Command(resume=user_answer),
    config=config,
)

assert final_state["answer"] == user_answer
assert "__interrupt__" not in final_state

print(f"中断内容：{interrupt_payload}")
print(f"恢复后答案：{final_state['answer']}")
print("Day 5 minimal interrupt passed.")

