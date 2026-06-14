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
      "No OpenRouter API key configured. Please set arcAgent.openRouterKey in VS Code settings."
    );
    onDone();
    return () => {};
  }

  const isGroq = apiKey.startsWith("gsk_") || apiKey.includes("groq");
  const hostname = isGroq ? "api.groq.com" : OPENROUTER_HOST;
  const path = isGroq ? "/openai/v1/chat/completions" : OPENROUTER_PATH;

  let model = getLLMModel();
  if (isGroq && (model.includes("gemini") || model.includes("deepseek"))) {
    model = "llama-3.3-70b-versatile";
  }

  const body = JSON.stringify({
    model,
    messages,
    stream: true,
    max_tokens: 2048,
    temperature: 0.4,
  });

  const options: https.RequestOptions = {
    hostname,
    path,
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
      "HTTP-Referer": "https://arc-lens.dev",
      "X-Title": "ARC Lens Pro",
      "Content-Length": Buffer.byteLength(body),
    },
  };

  let buffer = "";
  const req = https.request(options, (res) => {
    if (res.statusCode && res.statusCode >= 400) {
      let errBody = "";
      res.on("data", (d: Buffer) => (errBody += d.toString()));
      res.on("end", () => {
        onError(`OpenRouter API error ${res.statusCode}: ${errBody}`);
        onDone();
      });
      return;
    }

    res.on("data", (chunk: Buffer) => {
      buffer += chunk.toString();
      // SSE lines: "data: {...}\n\n"
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
          const delta = parsed?.choices?.[0]?.delta?.content;
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
