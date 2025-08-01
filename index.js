import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import * as net from "net";
import { type } from "os";

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
      }, 5000);

      client.on("connect", () => {
        const message = JSON.stringify(messageObject);

        client.write(message);
        client.end();
      });

      client.on("data", (data) => {
        buffer += data.toString();

        try {
          const response = JSON.parse(buffer);
          if (!resolved) {
            resolved = true;
            clearTimeout(timer);
            resolve(response);
          }
        } catch (e) {}
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

  async downloadAsset(asset_name, blend_url) {
    const messageObject = {
      type: "download-asset",
      asset_name: asset_name,
      blend_url: blend_url,
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

server.tool("get-asset-types-from-polyhaven", {}, async () => {
  try {
    const response = await fetch("https://api.polyhaven.com/types");
    const assetTypes = await response.json();
    return {
      content: [
        {
          type: "text",
          text: `Asset types fetched from PolyHaven:\n${JSON.stringify(
            assetTypes,
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
          text: `Failed to fetch asset types: ${
            error instanceof Error ? error.message : "Unknown error"
          }`,
        },
      ],
    };
  }
});

server.tool(
  "get-categories-from-polyhaven",
  {
    asset_type: z.string().describe("The asset type to fetch categories for"),
  },
  async ({ asset_type }) => {
    try {
      console.log("Received asset_type:", asset_type);
      const response = await fetch(
        `https://api.polyhaven.com/categories/${asset_type}`
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status} - ${response.statusText}`);
      }

      const categories = await response.json();

      return {
        content: [
          {
            type: "text",
            text: `Categories fetched for "${asset_type}":\n\n${JSON.stringify(
              categories,
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
            text: `Failed to fetch categories: ${
              error instanceof Error ? error.message : "Unknown error"
            }`,
          },
        ],
      };
    }
  }
);

server.tool(
  "get-asset-from-polyhaven",
  {
    asset_type: z.string().describe("The asset type to fetch"),
    category: z.string().describe("The category to fetch"),
  },
  async ({ asset_type, category }) => {
    try {
      const response = await fetch(
        `https://api.polyhaven.com/assets?t=${asset_type}&c=${category}`
      );
      const assets = await response.json();
      return {
        content: [
          {
            type: "text",
            text: `assets fetched are:\n\n${JSON.stringify(assets, null, 2)}`,
          },
        ],
      };
    } catch (error) {
      return {
        content: [
          {
            type: "text",
            text: `Failed to fetch assets: ${
              error instanceof Error ? error.message : "Unknown error"
            }`,
          },
        ],
      };
    }
  }
);

server.tool(
  "download-asset-from-polyhaven",
  {
    asset_name: z.string().describe("The asset name to download"),
    asset_type: z.string().describe("The asset type to download"),
    resolution: z
      .string()
      .optional()
      .describe(
        "Resolution preference (1k, 2k, 4k, 8k, etc.). Defaults to 1k for textures/hdris, blend for models"
      ),
    file_format: z
      .string()
      .optional()
      .describe(
        "The file format to download. Defaults to blend for models, jpg for textures, etc."
      ),
  },
  async ({ asset_name, asset_type, resolution, file_format }) => {
    try {
      const response = await fetch(
        `https://api.polyhaven.com/files/${asset_name}`
      );
      if (!response.ok) {
        throw new Error(
          `API request failed: ${response.status} ${response.statusText}`
        );
      }
      const assetFiles = await response.json();
      let defaultResolution, defaultFormat;
      if (asset_type == "hdris") {
        defaultResolution = "1K";
        defaultFormat = "hdr";
      }
      if (asset_type == "models") {
        defaultResolution = "1K";
        defaultFormat = "blend";
      }
      if (asset_type == "textures") {
        defaultResolution = "1K";
        defaultFormat = "jpg";
      } else {
        defaultResolution = "1K";
        defaultFormat = "jpg";
      }

      const targetResolution = resolution || defaultResolution;
      const targetFormat = file_format || defaultFormat;

      let downloadUrl = null;
      let includesData = null;

      // if (asset_type == "models" && targetFormat == "blend") {
      if (assetFiles.blend && assetFiles.blend[targetResolution]) {
        downloadUrl = assetFiles.blend[targetResolution].blend?.url;
        includesData =
          assetFiles.blend[targetResolution].blend?.include || null;
      }
      if (!downloadUrl && assetFiles.blend) {
        const availableResolutions = Object.keys(assetFiles.blend);
        if (availableResolutions.length > 0) {
          downloadUrl = assetFiles.blend[availableResolutions[0]].blend?.url;
          includesData =
            assetFiles.blend[availableResolutions[0]].blend?.include || null;
        }
      }
      // }
      if (downloadUrl) {
        // Send the data to Blender Python addon
        const messageObject = {
          type: "asset-data",
          asset_name: asset_name,
          asset_type: asset_type,
          resolution: targetResolution,
          format: targetFormat,
          blend_url: downloadUrl,
          includes: includesData,
          timestamp: new Date().toISOString(),
        };

        const blenderResponse = await blenderClient.sendMessage(messageObject);

        return {
          content: [
            {
              type: "text",
              text: `Asset data sent to Blender successfully!\n\nAsset name: ${asset_name}\nResolution: ${targetResolution}\nBlend URL: ${downloadUrl}\n\nIncludes data:\n${JSON.stringify(
                includesData,
                null,
                2
              )}\n\nBlender response:\n${JSON.stringify(
                blenderResponse,
                null,
                2
              )}`,
            },
          ],
        };
      } else {
        return {
          content: [
            {
              type: "text",
              text: `No suitable download URL found for asset: ${asset_name}\nAsset type: ${asset_type}\nResolution: ${targetResolution}\nFormat: ${targetFormat}`,
            },
          ],
        };
      }
    } catch (error) {
      return {
        content: [
          {
            type: "text",
            text: `Failed to get asset data: ${
              error instanceof Error ? error.message : "Unknown error"
            }`,
          },
        ],
      };
    }
  }
);

async function init() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

init().catch(console.error);
