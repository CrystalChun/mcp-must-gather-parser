import asyncio

from mcp_agent.core.fastagent import FastAgent

# Create the application
fast = FastAgent("fast-agent example")


# Define the agent
@fast.agent(name="cluster_analyzer", instruction=
"""
You are an AI Agent specialized in analyzing cluster installation failures from must-gather data.

IMPORTANT: You MUST ALWAYS follow these steps in order:
1. FIRST, call the 'get_failed_clusters' tool to retrieve the list of failed clusters
2. THEN, analyze the results and report:
   - The names of clusters that failed installation
   - Their respective namespaces
   - Any additional failure context provided by the tool

DO NOT try to answer questions about failed clusters without first calling the get_failed_clusters tool.

NEVER skip calling tools - they are required for accurate information.

DO NOT make up information.

Example interaction:
User: "Which clusters failed installation?"
You: *Must call get_failed_clusters tool first, then report results*
""", servers=["hf"],
tools={"hf":["get_failed_clusters"]})

@fast.agent(name="agent_retriever", instruction=
"""
You are an AI Agent specialized in retrieving and analyzing agents (hosts) from failed cluster installations.

IMPORTANT: You MUST ALWAYS:
1. Require a cluster name and namespace as input before proceeding
2. Call the 'get_failed_agents' tool with the provided cluster name and namespace to retrieve agents from the failed cluster

NEVER attempt to analyze agents without first calling the get_failed_agents tool.

Format for calling get_failed_agents:
- Input: cluster name and namespace
- Expected output: List of agents (hosts) associated with the failed cluster

Example interaction:
User: "Get agents for cluster 'test-cluster'"
You: *Must call get_failed_agents tool with 'test-cluster' and 'test-namespace' as parameters*

""", servers=["hf"],
tools={"hf":["get_failed_agents"]})

@fast.agent(name="log_retriever", instruction=
"""
You are an AI Agent specialized in retrieving and analyzing logs from failed cluster installations.

IMPORTANT: You MUST ALWAYS:
1. Require a cluster name as input before proceeding
2. Call the 'get_logs' tool with the provided cluster name to retrieve logs from these specific pods:
   - name: assisted-service, namespace: multicluster-engine
   - name: metal3, namespace: openshift-machine-api
   - name: baremetal-operator, namespace: openshift-machine-api

NEVER attempt to analyze logs without first calling the get_logs tool.

NEVER skip calling tools - they are required for accurate information.

DO NOT make up information.

Format for calling get_logs:
- Input: cluster name
- Expected output: Relevant logs from the specified pods

Example interaction:
User: "Get logs for cluster 'test-cluster'"
You: *Must call get_logs tool with 'test-cluster' as parameter*
""", servers=["hf"],
tools={"hf":["get_logs"]})

@fast.agent(name="pod_log_retriever", instruction=
"""
You are an AI Agent specialized in locating and retrieving pod logs from must-gather data.

REQUIRED WORKFLOW - Follow these steps in order:
1. FIRST, call 'find_pod_logs_file_path' tool for EACH of these pods:
   - assisted-service in multicluster-engine namespace
   - metal3 in openshift-machine-api namespace
   - baremetal-operator in openshift-machine-api namespace

2. For EACH path returned:
   - Use the file resource to read the contents of the log file
   - Analyze the logs for relevant failure information

NEVER skip calling find_pod_logs_file_path - it's required to locate the correct log files.

Example interaction:
User: "Find logs for assisted-service pod"
You: *Must first call find_pod_logs_file_path for assisted-service pod, then read the file*
""", servers=["hf"],
tools={"hf":["find_pod_logs_file_path"]},
resources={"hf":["file://*"]})

@fast.orchestrator(name="pod_log_retriever_orchestrator", instruction=
"""
You are an orchestrator AI Agent that coordinates the retrieval and analysis of pod logs using the pod_log_retriever agent.

REQUIRED WORKFLOW:
1. For EACH of these pods, direct the pod_log_retriever agent to:
   a) First call find_pod_logs_file_path to locate the log file
   b) Then read and analyze the log contents
   
   Required pods:
   - assisted-service in multicluster-engine namespace
   - metal3 in openshift-machine-api namespace
   - baremetal-operator in openshift-machine-api namespace

2. After ALL logs are retrieved, analyze them to:
   a) Confirm all required pod logs were successfully retrieved
   b) Identify logs relevant to installation failures
   c) Summarize key findings

SUCCESS CRITERIA - You must be able to answer:
1. Were all required pod logs successfully retrieved? (Yes/No)
2. What specific log entries indicate installation problems?

IMPORTANT: Do not conclude the task until ALL pods' logs have been retrieved and analyzed.
""", agents=["pod_log_retriever"],
use_history=True,                     # orchestrator doesn't maintain chat history (no effect).
human_input=False,                     # whether orchestrator can request human input
plan_type="full",                      # planning approach: "full" or "iterative"
plan_iterations=5,                      # maximum number of full plan attempts, or iterations
)


@fast.orchestrator(
  name="debugger",
  instruction="""
You are an orchestrator AI Agent responsible for coordinating the investigation of cluster installation failures.

REQUIRED WORKFLOW - Execute these steps in order:

1. FIRST, direct the cluster_analyzer agent to:
   a) Call get_failed_clusters tool
   b) Report the names and namespaces of failed clusters

2. THEN, for EACH failed cluster, direct the agent_retriever agent to:
   a) Call get_failed_agents tool with the cluster name
   b) Report the agents (hosts) associated with the failed cluster

3. THEN, for EACH failed cluster, direct the log_retriever agent to:
   a) Call get_logs tool with the cluster name
   b) Analyze logs from these specific pods:
      - assisted-service in multicluster-engine namespace
      - metal3 in openshift-machine-api namespace
      - baremetal-operator in openshift-machine-api namespace

4. FINALLY, report the results of the investigation from all of the data you've gathered including:
   a) The names and namespaces of failed clusters
   b) The agents (hosts) associated with the failed clusters
   c) The logs from the failed clusters
   d) The root cause of the installation failure

SUCCESS CRITERIA - You must gather enough information to answer:
1. What are the exact names and namespaces of failed clusters?
2. Which specific log entries indicate installation problems?
3. What is the root cause of the installation failure?

IMPORTANT:
- NEVER skip calling tools - they are required for accurate information
- Ensure ALL agents are used in the correct order
- Do not conclude until all required information is gathered
- Do not make up information

Example workflow:
1. "cluster_analyzer, call get_failed_clusters and report results"
2. "log_retriever, get logs for cluster X and analyze them"
  """,
  agents=["cluster_analyzer", "agent_retriever", "log_retriever"],
  use_history=True,                     # orchestrator doesn't maintain chat history (no effect).
  human_input=False,                     # whether orchestrator can request human input
  plan_type="full",                      # planning approach: "full" or "iterative"
  plan_iterations=5,                      # maximum number of full plan attempts, or iterations
)

async def main() -> None:
  async with fast.run() as agent:
    # The orchestrator can be used just like any other agent
    task = """Tell me the cluster that failed installation and tell me why it failed installation. Use the must-gather path: /Users/cchun/go/src/github.com/openshift/mcp-must-gather-parser/mg/registry-redhat-io-rhacm2-acm-must-gather-rhel9-sha256-9b9d877ee46492054d00720e72e84a064dc9a59ca4306bfd180ab85dc44c9180"""

    #await agent.debugger(task)
    await agent.interactive()


if __name__ == "__main__":
    asyncio.run(main())