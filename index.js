import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({
  name: "MCP_DEMO",
  version: "1.0.0",
});

server.tool(
  "send-code",
  {
    code: z.string(),
  },
  async ({ code }) => {
    return { content: [{ type: "text", text: code }] };
  }
);

async function init() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

init();
