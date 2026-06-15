import * as https from "https";
import { getOpenRouterKey, getLLMModel } from "./licenseManager";

const OPENROUTER_HOST = "openrouter.ai";
const OPENROUTER_PATH = "/api/v1/chat/completions";

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

/**
 * Sends a streaming chat completion request to OpenRouter.
 * Calls `onChunk` with each text delta as it arrives,
 * and `onDone` when the stream ends.
 * Returns a cancel function to abort the request.
 */
export function streamChatCompletion(
  messages: ChatMessage[],
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: string) => void
): () => void {
  const apiKey = getOpenRouterKey();
  if (!apiKey) {
    onError(
      "No API key configured. Please set arcAgent.openRouterKey in VS Code settings."
    );
    onDone();
    return () => {};
  }

  const isGroq = apiKey.startsWith("gsk_") || apiKey.includes("groq");
  const isAnthropic = apiKey.startsWith("sk-ant-") || apiKey.includes("anthropic");
  const isGemini = apiKey.startsWith("AIzaSy") || apiKey.includes("gemini") || apiKey.includes("google");
  const isOpenAI = (apiKey.startsWith("sk-") && !apiKey.startsWith("sk-or-") && !apiKey.startsWith("sk-ant-")) || apiKey.includes("openai");

  let hostname = OPENROUTER_HOST;
  let path = OPENROUTER_PATH;
  let model = getLLMModel();
  let headers: { [key: string]: string } = {
    "Content-Type": "application/json"
  };

  if (isGroq) {
    hostname = "api.groq.com";
    path = "/openai/v1/chat/completions";
    headers["Authorization"] = `Bearer ${apiKey}`;
    if (!model.includes("llama") && !model.includes("mixtral")) {
      model = "llama-3.3-70b-versatile";
    }
  } else if (isAnthropic) {
    hostname = "api.anthropic.com";
    path = "/v1/messages";
    headers["x-api-key"] = apiKey;
    headers["anthropic-version"] = "2023-06-01";
    if (!model.includes("claude")) {
      model = "claude-3-5-sonnet-20241022";
    }
  } else if (isGemini) {
    hostname = "generativelanguage.googleapis.com";
    path = "/v1beta/openai/chat/completions";
    headers["Authorization"] = `Bearer ${apiKey}`;
    if (!model.includes("gemini")) {
      model = "gemini-1.5-flash";
    }
  } else if (isOpenAI) {
    hostname = "api.openai.com";
    path = "/v1/chat/completions";
    headers["Authorization"] = `Bearer ${apiKey}`;
    if (!model.startsWith("gpt-")) {
      model = "gpt-4o-mini";
    }
  } else {
    // OpenRouter (default)
    hostname = OPENROUTER_HOST;
    path = OPENROUTER_PATH;
    headers["Authorization"] = `Bearer ${apiKey}`;
    headers["HTTP-Referer"] = "https://arc-lens.dev";
    headers["X-Title"] = "ARC Lens Pro";
  }

  let body: string;
  if (isAnthropic) {
    const systemMessage = messages.find(m => m.role === "system")?.content;
    const chatMessages = messages.filter(m => m.role !== "system");
    body = JSON.stringify({
      model,
      messages: chatMessages,
      system: systemMessage,
      stream: true,
      max_tokens: 2048,
      temperature: 0.4,
    });
  } else {
    body = JSON.stringify({
      model,
      messages,
      stream: true,
      max_tokens: 2048,
      temperature: 0.4,
    });
  }

  headers["Content-Length"] = String(Buffer.byteLength(body));

  const options: https.RequestOptions = {
    hostname,
    path,
    method: "POST",
    headers,
  };

  let buffer = "";
  const req = https.request(options, (res) => {
    if (res.statusCode && res.statusCode >= 400) {
      let errBody = "";
      res.on("data", (d: Buffer) => (errBody += d.toString()));
      res.on("end", () => {
        onError(`API error ${res.statusCode}: ${errBody}`);
        onDone();
      });
      return;
    }

    res.on("data", (chunk: Buffer) => {
      buffer += chunk.toString();
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith("data: ")) continue;
        const data = trimmed.slice(6);
        if (data === "[DONE]") {
          onDone();
          return;
        }
        try {
          const parsed = JSON.parse(data);
          const delta = parsed?.choices?.[0]?.delta?.content || parsed?.delta?.text;
          if (delta) {
            onChunk(delta);
          }
        } catch {
          // skip malformed SSE lines
        }
      }
    });

    res.on("end", () => {
      onDone();
    });

    res.on("error", (err: Error) => {
      onError(err.message);
      onDone();
    });
  });

  req.on("error", (err: Error) => {
    onError(err.message);
    onDone();
  });

  req.write(body);
  req.end();

  // Return cancel function
  return () => {
    req.destroy();
  };
}
