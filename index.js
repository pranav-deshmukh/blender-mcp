import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import * as net from "net";

const server = new McpServer({
  name: "BLENDER_MCP",
  version: "1.0.0",
});

// Simple TCP client to connect to Blender
class BlenderClient {
  host = "localhost";
  port = 8765;

  async sendCode(code) {
    return new Promise((resolve, reject) => {
      // Create TCP connection (connects to your Blender addon)
      const client = net.createConnection(this.port, this.host);

      client.on("connect", () => {
        console.log("Connected to Blender addon");

        // Send JSON message (same format your Python code expects)
        const message = JSON.stringify({
          type: "code",
          code: code,
          timestamp: new Date().toISOString(),
        });

        console.log("Sending to Blender:", message);
        client.write(message);
      });

      let buffer = "";

      client.on("data", (data) => {
        buffer += data.toString();

        if (buffer.includes("\n")) {
          try {
            const cleanResponse = buffer.trim(); // Remove \n
            const parsed = JSON.parse(cleanResponse);
            console.log("Response from Blender:", parsed);
            resolve(parsed);
          } catch (err) {
            console.error("Failed to parse response JSON:", buffer);
            reject(err);
          } finally {
            client.end();
          }
        }
      });

      client.on("error", (err) => {
        console.error("Connection error:", err.message);
        reject(err);
      });

      client.on("close", () => {
        console.log("Connection to Blender closed");
      });
    });
  }
}

const blenderClient = new BlenderClient();

// MCP tool to send code to Blender
server.tool(
  "send-code-to-blender",
  {
    code: z.string().describe("Python code to send to Blender"),
  },
  async ({ code }) => {
    try {
      const response = await blenderClient.sendCode(code);

      return {
        content: [
          {
            type: "text",
            text: `Code sent to Blender successfully!\n\nSent code:\n${code}\n\nBlender response:\n${response}`,
          },
        ],
      };
    } catch (error) {
      return {
        content: [
          {
            type: "text",
            text: `Failed to send code to Blender: ${
              error instanceof Error ? error.message : "Unknown error"
            }\n\nCode that failed to send:\n${code}`,
          },
        ],
      };
    }
  }
);

// Test connection tool
server.tool("test-blender-connection", {}, async () => {
  try {
    const response = await blenderClient.sendCode('print("Hello from MCP!")');
    return {
      content: [
        {
          type: "text",
          text: `Connection test successful! Blender response: ${response}`,
        },
      ],
    };
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: `Connection test failed: ${
            error instanceof Error ? error.message : "Unknown error"
          }`,
        },
      ],
    };
  }
});

async function init() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.log("MCP Server started - ready to communicate with Blender!");
}

init().catch(console.error);
