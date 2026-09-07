/**
 * Structured Logger for pilot-memory Worker Service
 * Provides readable, traceable logging with correlation IDs and data flow tracking
 */

import { appendFileSync, existsSync, mkdirSync, readFileSync } from "fs";
import { join } from "path";
import { memoryDataDir } from "../shared/memory-data-dir.js";

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  SILENT = 4,
}

type Component =
  | "HOOK"
  | "WORKER"
  | "SDK"
  | "PARSER"
  | "DB"
  | "SYSTEM"
  | "HTTP"
  | "SESSION"
  | "CHROMA"
  | "FOLDER_INDEX"
  | "CURSOR"
  | "CHROMA_SYNC"
  | "QUEUE"
  | "CONSOLE"
  | "IMPORT"
  | "EMBEDDING"
  | "VECTOR_SYNC"
  | "BRANCH"
  | "SEARCH"
  | "CONFIG"
  | "MEMORY"
  | "PROJECT"
  | "PROJECT_NAME"
  | "SECURITY"
  | "SETTINGS"
  | "SUBSCRIPTION"
  | "VECTOR"
  | "VIEWER"
  | "RETENTION"
  | "BACKUP"
  | "CLEANUP"
  | "DATA"
  | "VECTOR_DB_GUARD"
  | "FEEDBACK_POLL"
  | "CODEX_PARSER";

interface LogContext {
  sessionId?: number;
  memorySessionId?: string;
  correlationId?: string;
  [key: string]: any;
}

const DEFAULT_DATA_DIR = memoryDataDir();

class Logger {
  private level: LogLevel | null = null;
  private useColor: boolean;
  private logFilePath: string | null = null;
  private logFileInitialized: boolean = false;

  constructor() {
    this.useColor = process.stdout.isTTY ?? false;
  }

  /**
   * Initialize log file path and ensure directory exists (lazy initialization)
   */
  private ensureLogFileInitialized(): void {
    if (this.logFileInitialized) return;
    this.logFileInitialized = true;

    try {
      const logsDir = join(DEFAULT_DATA_DIR, "logs");

      if (!existsSync(logsDir)) {
        mkdirSync(logsDir, { recursive: true });
      }

      const date = new Date().toISOString().split("T")[0];
      this.logFilePath = join(logsDir, `pilot-memory-${date}.log`);
    } catch (error) {
      console.error("[LOGGER] Failed to initialize log file:", error);
      this.logFilePath = null;
    }
  }

  /**
   * Lazy-load log level from settings file
   * Uses direct file reading to avoid circular dependency with SettingsDefaultsManager
   */
  private getLevel(): LogLevel {
    if (this.level === null) {
      try {
        const settingsPath = join(DEFAULT_DATA_DIR, "settings.json");
        if (existsSync(settingsPath)) {
          const settingsData = readFileSync(settingsPath, "utf-8");
          const settings = JSON.parse(settingsData);
          const envLevel = (settings.CLAUDE_PILOT_LOG_LEVEL || "INFO").toUpperCase();
          this.level = LogLevel[envLevel as keyof typeof LogLevel] ?? LogLevel.INFO;
        } else {
          this.level = LogLevel.INFO;
        }
      } catch (error) {
        this.level = LogLevel.INFO;
      }
    }
    return this.level;
  }

  /**
   * Create correlation ID for tracking an observation through the pipeline
   */
  correlationId(sessionId: number, observationNum: number): string {
    return `obs-${sessionId}-${observationNum}`;
  }

  /**
   * Create session correlation ID
   */
  sessionId(sessionId: number): string {
    return `session-${sessionId}`;
  }

  /**
   * Format data for logging - create compact summaries instead of full dumps
   */
  private formatData(data: any): string {
    if (data === null || data === undefined) return "";
    if (typeof data === "string") return data;
    if (typeof data === "number") return data.toString();
    if (typeof data === "boolean") return data.toString();

    if (typeof data === "object") {
      if (data instanceof Error) {
        return this.getLevel() === LogLevel.DEBUG ? `${data.message}\n${data.stack}` : data.message;
      }

      if (Array.isArray(data)) {
        return `[${data.length} items]`;
      }

      const keys = Object.keys(data);
      if (keys.length === 0) return "{}";
      if (keys.length <= 3) {
        return JSON.stringify(data);
      }
      return `{${keys.length} keys: ${keys.slice(0, 3).join(", ")}...}`;
    }

    return String(data);
  }

  /**
   * Format a tool name and input for compact display
   */
  formatTool(toolName: string, toolInput?: any): string {
    if (!toolInput) return toolName;

    let input = toolInput;
    if (typeof toolInput === "string") {
      try {
        input = JSON.parse(toolInput);
      } catch {
        input = toolInput;
      }
    }

    if (toolName === "Bash" && input.command) {
      return `${toolName}(${input.command})`;
    }

    if (input.file_path) {
      return `${toolName}(${input.file_path})`;
    }

    if (input.notebook_path) {
      return `${toolName}(${input.notebook_path})`;
    }

    if (toolName === "Glob" && input.pattern) {
      return `${toolName}(${input.pattern})`;
    }

    if (toolName === "Grep" && input.pattern) {
      return `${toolName}(${input.pattern})`;
    }

    if (input.url) {
      return `${toolName}(${input.url})`;
    }

    if (input.query) {
      return `${toolName}(${input.query})`;
    }

    if (toolName === "Task") {
      if (input.subagent_type) {
        return `${toolName}(${input.subagent_type})`;
      }
      if (input.description) {
        return `${toolName}(${input.description})`;
      }
    }

    if (toolName === "Skill" && input.skill) {
      return `${toolName}(${input.skill})`;
    }

    if (toolName === "LSP" && input.operation) {
      return `${toolName}(${input.operation})`;
    }

    return toolName;
  }

  /**
   * Format timestamp in local timezone (YYYY-MM-DD HH:MM:SS.mmm)
   */
  private formatTimestamp(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    const seconds = String(date.getSeconds()).padStart(2, "0");
    const ms = String(date.getMilliseconds()).padStart(3, "0");
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}.${ms}`;
  }

  /**
   * Core logging method
   */
  private log(level: LogLevel, component: Component, message: string, context?: LogContext, data?: any): void {
    if (level < this.getLevel()) return;

    this.ensureLogFileInitialized();

    const timestamp = this.formatTimestamp(new Date());
    const levelStr = LogLevel[level].padEnd(5);
    const componentStr = component.padEnd(6);

    let correlationStr = "";
    if (context?.correlationId) {
      correlationStr = `[${context.correlationId}] `;
    } else if (context?.sessionId) {
      correlationStr = `[session-${context.sessionId}] `;
    }

    let dataStr = "";
    if (data !== undefined && data !== null) {
      if (data instanceof Error) {
        dataStr = this.getLevel() === LogLevel.DEBUG ? `\n${data.message}\n${data.stack}` : ` ${data.message}`;
      } else if (this.getLevel() === LogLevel.DEBUG && typeof data === "object") {
        dataStr = "\n" + JSON.stringify(data, null, 2);
      } else {
        dataStr = " " + this.formatData(data);
      }
    }

    let contextStr = "";
    if (context) {
      const { sessionId, memorySessionId, correlationId, ...rest } = context;
      if (Object.keys(rest).length > 0) {
        const pairs = Object.entries(rest).map(([k, v]) => `${k}=${v}`);
        contextStr = ` {${pairs.join(", ")}}`;
      }
    }

    const logLine = `[${timestamp}] [${levelStr}] [${componentStr}] ${correlationStr}${message}${contextStr}${dataStr}`;

    if (this.logFilePath) {
      try {
        appendFileSync(this.logFilePath, logLine + "\n", "utf8");
      } catch (error) {
        process.stderr.write(`[LOGGER] Failed to write to log file: ${error}\n`);
        // Avoid retrying a failing synchronous write on every log call. This
        // commonly happens in sandboxed/read-only environments and repeated
        // appendFileSync exceptions can flood stderr and slow the worker down.
        // Fall back to stderr for subsequent log lines.
        this.logFilePath = null;
      }
    } else {
      process.stderr.write(logLine + "\n");
    }
  }

  debug(component: Component, message: string, context?: LogContext, data?: any): void {
    this.log(LogLevel.DEBUG, component, message, context, data);
  }

  info(component: Component, message: string, context?: LogContext, data?: any): void {
    this.log(LogLevel.INFO, component, message, context, data);
  }

  warn(component: Component, message: string, context?: LogContext, data?: any): void {
    this.log(LogLevel.WARN, component, message, context, data);
  }

  error(component: Component, message: string, context?: LogContext, data?: any): void {
    this.log(LogLevel.ERROR, component, message, context, data);
  }

  /**
   * Log data flow: input → processing
   */
  dataIn(component: Component, message: string, context?: LogContext, data?: any): void {
    this.info(component, `→ ${message}`, context, data);
  }

  /**
   * Log data flow: processing → output
   */
  dataOut(component: Component, message: string, context?: LogContext, data?: any): void {
    this.info(component, `← ${message}`, context, data);
  }

  /**
   * Log successful completion
   */
  success(component: Component, message: string, context?: LogContext, data?: any): void {
    this.info(component, `✓ ${message}`, context, data);
  }

  /**
   * Log failure
   */
  failure(component: Component, message: string, context?: LogContext, data?: any): void {
    this.error(component, `✗ ${message}`, context, data);
  }

  /**
   * Log timing information
   */
  timing(component: Component, message: string, durationMs: number, context?: LogContext): void {
    this.info(component, `⏱ ${message}`, context, { duration: `${durationMs}ms` });
  }

  /**
   * Happy Path Error - logs when the expected "happy path" fails but we have a fallback
   *
   * Semantic meaning: "When the happy path fails, this is an error, but we have a fallback."
   *
   * Use for:
   * ✅ Unexpected null/undefined values that should theoretically never happen
   * ✅ Defensive coding where silent fallback is acceptable
   * ✅ Situations where you want to track unexpected nulls without breaking execution
   *
   * DO NOT use for:
   * ❌ Nullable fields with valid default behavior (use direct || defaults)
   * ❌ Critical validation failures (use logger.warn or throw Error)
   * ❌ Try-catch blocks where error is already logged (redundant)
   *
   * @param component - Component where error occurred
   * @param message - Error message describing what went wrong
   * @param context - Optional context (sessionId, correlationId, etc)
   * @param data - Optional data to include
   * @param fallback - Value to return (defaults to empty string)
   * @returns The fallback value
   */
  happyPathError<T = string>(
    component: Component,
    message: string,
    context?: LogContext,
    data?: any,
    fallback: T = "" as T,
  ): T {
    const stack = new Error().stack || "";
    const stackLines = stack.split("\n");
    const callerLine = stackLines[2] || "";
    const callerMatch = callerLine.match(/at\s+(?:.*\s+)?\(?([^:]+):(\d+):(\d+)\)?/);
    const location = callerMatch ? `${callerMatch[1].split("/").pop()}:${callerMatch[2]}` : "unknown";

    const enhancedContext = {
      ...context,
      location,
    };

    this.warn(component, `[HAPPY-PATH] ${message}`, enhancedContext, data);

    return fallback;
  }
}

export const logger = new Logger();
