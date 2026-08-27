
import {
  BRIDGE_PROTOCOL_VERSION,
  bridgeErrorFromUnknown,
  handleBridgeRequest,
  MAX_BRIDGE_REQUEST_BYTES,
} from "@/streamlit/bridge";

async function readRequest(): Promise<unknown> {
  process.stdin.setEncoding("utf8");
  let body = "";
  let size = 0;
  for await (const chunk of process.stdin) {
    const text = String(chunk);
    size += Buffer.byteLength(text, "utf8");
    if (size > MAX_BRIDGE_REQUEST_BYTES) {
      throw Object.assign(new Error("Bridge request too large."), {
        code: "REQUEST_TOO_LARGE",
      });
    }
    body += text;
  }
  if (!body.trim()) {
    throw Object.assign(new Error("Bridge request is empty."), {
      code: "INVALID_REQUEST",
    });
  }
  try {
    return JSON.parse(body);
  } catch {
    throw Object.assign(new Error("Bridge request is not valid JSON."), {
      code: "INVALID_REQUEST",
    });
  }
}

async function main(): Promise<void> {
  try {
    const response = await handleBridgeRequest(await readRequest());
    process.stdout.write(JSON.stringify(response));
  } catch (reason) {
    process.stdout.write(
      JSON.stringify({
        protocolVersion: BRIDGE_PROTOCOL_VERSION,
        requestId: "unknown",
        success: false,
        error: bridgeErrorFromUnknown(reason),
      }),
    );
  }
}

void main();
