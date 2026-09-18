"""用一个最小计数图理解 LangGraph 的基本执行过程。"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class CounterState(TypedDict):
    """最小图在节点之间共享的业务状态。"""

    count: int


def add_one(state: CounterState) -> dict[str, int]:
    """读取当前计数，并返回需要写回 State 的部分更新。"""

    return {"count": state["count"] + 1}


builder = StateGraph(CounterState)
builder.add_node("add_one", add_one)
builder.add_edge(START, "add_one")
builder.add_edge("add_one", END)
graph = builder.compile()


if __name__ == "__main__":
    result = graph.invoke({"count": 1})
    assert result["count"] == 2
    print(result)
