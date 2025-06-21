import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import * as net from "net";

const server = new McpServer({
  name: "BLENDER_MCP",
  version: "1.0.0",
});

class BlenderClient {
  host = "localhost";
  port = 8765;

  async sendMessage(messageObject) {
    return new Promise((resolve, reject) => {
      const client = net.createConnection(this.port, this.host);
      let buffer = "";
      let resolved = false;

      const timer = setTimeout(() => {
        if (!resolved) {
          resolved = true;
          client.destroy();
          reject(new Error("Timed out waiting for Blender response"));
        }
      }, 5000); // Reduced timeout

      client.on("connect", () => {
        console.log("Connected to Blender");
        const message = JSON.stringify(messageObject);

        client.write(message);
        client.end();
      });

      client.on("data", (data) => {
        buffer += data.toString();
        console.log("Received data from Blender:", data.toString());

        try {
          const response = JSON.parse(buffer);
          if (!resolved) {
            resolved = true;
            clearTimeout(timer);
            resolve(response);
          }
        } catch (e) {
          console.log("Incomplete JSON, waiting for more data");
        }
      });

      client.on("error", (err) => {
        console.error("Client error:", err);
        if (!resolved) {
          resolved = true;
          clearTimeout(timer);
          reject(err);
        }
      });

      client.on("close", () => {
        console.log("Connection closed by Blender");
        if (!resolved) {
          resolved = true;
          clearTimeout(timer);
          if (buffer) {
            try {
              const response = JSON.parse(buffer);
              resolve(response);
            } catch (e) {
              reject(
                new Error(`Connection closed with invalid JSON: ${buffer}`)
              );
            }
          } else {
            reject(new Error("Connection closed without any response"));
          }
        }
      });
    });
  }
  async sendCode(code) {
    const messageObject = {
      type: "code",
      code: code,
      timestamp: new Date().toISOString(),
    };
    return this.sendMessage(messageObject);
  }

  async fetchScene() {
    const messageObject = {
      type: "fetch-scene",
      timestamp: new Date().toISOString(),
    };
    return this.sendMessage(messageObject);
  }
}

const blenderClient = new BlenderClient();

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
            text: `Code sent to Blender successfully!\n\nSent code:\n${code}\n\nBlender response:\n${JSON.stringify(
              response,
              null,
              2
            )}`,
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

server.tool("test-blender-connection", {}, async () => {
  try {
    const response = await blenderClient.sendCode('print("Hello from MCP!")');
    return {
      content: [
        {
          type: "text",
          text: `Connection test successful! Blender response: ${JSON.stringify(
            response,
            null,
            2
          )}`,
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

server.tool("fetch-scene-from-blender", {}, async () => {
  try {
    console.log("Fetching scene from Blender...");
    const response = await blenderClient.fetchScene();

    return {
      content: [
        {
          type: "text",
          text: `Scene fetched from Blender:\n${JSON.stringify(
            response,
            null,
            2
          )}`,
        },
      ],
    };
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: `Failed to fetch scene: ${
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
