import asyncio

from mcp_agent.core.fastagent import FastAgent

# Create the application
fast = FastAgent("fast-agent example")


# Define the agent
@fast.agent(name="helpful", instruction=
"""You are a helpful AI Agent that can determine clusters that failed installation in a must-gather directory and can detect the logs that are relevant to the failure in the same must-gather directory.

You will have access to tools that you can call to get the clusters that failed in the must-gather directory and the logs that are relevant to the failure of the cluster.

You will need to use the tools to get the clusters that failed in the must-gather directory and the logs that are relevant to the failure of the cluster.

You will need to use the tools to get the logs that are relevant to the failure of the cluster. You will get logs with a chunk size of 25 lines. Please provide the start index and chunk size when you call the tool.

""", servers=["hf"])
@fast.agent(name="fs", instruction="You can look at the filesystem and get the logs that are relevant to the failure of a cluster", servers=["filesystem"])
@fast.orchestrator(
  name="log_analyzer",                   # name of the orchestrator
  instruction="find the cluster that failed installation and get all the logs that are relevant to the failure ",             # base instruction for the orchestrator
  agents=["helpful"],           # list of agent names this orchestrator can use
  use_history=False,                     # orchestrator doesn't maintain chat history (no effect).
  human_input=False,                     # whether orchestrator can request human input
  plan_type="iterative",                      # planning approach: "full" or "iterative"
  plan_iterations=20,                      # maximum number of full plan attempts, or iterations
)
async def main() -> None:
  async with fast.run() as agent:
    # The orchestrator can be used just like any other agent
    #task = """Can you tell me the failed cluster and get the logs that are relevant to the failure in the must-gather directory: """

    #await agent.log_analyzer(task)
    await agent.interactive()


if __name__ == "__main__":
    asyncio.run(main())