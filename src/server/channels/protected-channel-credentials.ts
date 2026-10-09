import { lstat, readFile, realpath } from "node:fs/promises";
import { homedir } from "node:os";
import { isAbsolute, join, relative, resolve } from "node:path";

import { ChannelConnectorError } from "@/server/channels/errors";

export const CHANNEL_CREDENTIALS_PATH = join(
  homedir(),
  ".agentic-marketing",
  "channel-credentials.json",
);

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isInsideWorkspace(path: string): boolean {
  const fromWorkspace = relative(resolve(process.cwd()), resolve(path));
  return fromWorkspace === "" ||
    (!fromWorkspace.startsWith("..") && !isAbsolute(fromWorkspace));
}

export async function assertOutsideWorkspace(path: string): Promise<void> {
  if (isInsideWorkspace(path)) {
    throw new ChannelConnectorError(
      "CREDENTIALS_UNSAFE",
      "Channel credentials and OAuth tokens must be outside the workspace.",
      503,
    );
  }
  try {
    const actualParent = await realpath(resolve(path, ".."));
    if (isInsideWorkspace(actualParent)) {
      throw new ChannelConnectorError(
        "CREDENTIALS_UNSAFE",
        "Channel credentials and OAuth tokens must be outside the workspace.",
        503,
      );
    }
  } catch (error) {
    if (error instanceof ChannelConnectorError) throw error;
    if (record(error) && error.code === "ENOENT") return;
    throw new ChannelConnectorError(
      "CREDENTIALS_UNSAFE",
      "The protected channel credential location is unavailable.",
      503,
    );
  }
}

export async function loadProtectedChannelCredentials(
  channel:
    | "YouTube"
    | "Google Ads"
    | "WeChat Official Account"
    | "Account Engagement" = "YouTube",
): Promise<unknown> {
  await assertOutsideWorkspace(CHANNEL_CREDENTIALS_PATH);
  let info;
  try {
    info = await lstat(CHANNEL_CREDENTIALS_PATH);
  } catch (error) {
    if (record(error) && error.code === "ENOENT") {
      throw new ChannelConnectorError(
        "CREDENTIALS_MISSING",
        `Configure the protected ${channel} credentials before connecting.`,
        503,
      );
    }
    throw new ChannelConnectorError(
      "CREDENTIALS_UNSAFE",
      `The protected ${channel} credential file is inaccessible.`,
      503,
    );
  }
  if (
    !info.isFile() ||
    info.size > 8192 ||
    (process.platform !== "win32" && (info.mode & 0o077) !== 0)
  ) {
    throw new ChannelConnectorError(
      "CREDENTIALS_UNSAFE",
      `The protected ${channel} credential file is unsafe.`,
      503,
    );
  }
  try {
    return JSON.parse(await readFile(CHANNEL_CREDENTIALS_PATH, "utf8")) as unknown;
  } catch (error) {
    if (error instanceof ChannelConnectorError) throw error;
    throw new ChannelConnectorError(
      "CREDENTIALS_INVALID",
      `The protected ${channel} OAuth credentials are invalid.`,
      503,
    );
  }
}
