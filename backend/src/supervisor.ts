import { spawn, ChildProcess } from "node:child_process";
import { EventEmitter } from "node:events";

export interface LogEntry {
  timestamp: string;
  source: "bridge" | "manager" | "kaspad";
  level: "info" | "warn" | "error";
  message: string;
}

export class BridgeSupervisor extends EventEmitter {
  private childProcess: ChildProcess | null = null;
  private isRunning: boolean = false;
  private logBuffer: LogEntry[] = [];
  private readonly MAX_LOGS = 1000;
  private bridgeBinaryPath: string;
  private configPath: string;

  constructor(bridgeBinaryPath: string = "/usr/local/bin/stratum-bridge", configPath: string = "./config.yaml") {
    super();
    this.bridgeBinaryPath = bridgeBinaryPath;
    this.configPath = configPath;
  }

  public getStatus() {
    return {
      running: this.isRunning,
      pid: this.childProcess?.pid ?? null,
      binaryPath: this.bridgeBinaryPath,
      configPath: this.configPath,
    };
  }

  public getLogs(limit: number = 200): LogEntry[] {
    return this.logBuffer.slice(-limit);
  }

  public addLog(source: LogEntry["source"], level: LogEntry["level"], message: string) {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      source,
      level,
      message: message.trim(),
    };
    this.logBuffer.push(entry);
    if (this.logBuffer.length > this.MAX_LOGS) {
      this.logBuffer.shift();
    }
    this.emit("log", entry);
  }

  public async start(): Promise<boolean> {
    if (this.isRunning) return true;

    try {
      this.addLog("manager", "info", `Starting Stratum Bridge process: ${this.bridgeBinaryPath}`);
      // In production/docker this executes the stratum-bridge binary
      this.childProcess = spawn(this.bridgeBinaryPath, ["--config", this.configPath], {
        stdio: ["ignore", "pipe", "pipe"],
      });

      this.isRunning = true;

      this.childProcess.stdout?.on("data", (data) => {
        this.addLog("bridge", "info", data.toString());
      });

      this.childProcess.stderr?.on("data", (data) => {
        this.addLog("bridge", "warn", data.toString());
      });

      this.childProcess.on("exit", (code, signal) => {
        this.isRunning = false;
        this.childProcess = null;
        this.addLog("manager", "warn", `Stratum bridge exited with code ${code}, signal ${signal}`);
        this.emit("exit", { code, signal });
      });

      this.childProcess.on("error", (err) => {
        this.isRunning = false;
        this.childProcess = null;
        this.addLog("manager", "error", `Stratum bridge process error: ${err.message}`);
      });

      return true;
    } catch (err: any) {
      this.isRunning = false;
      this.addLog("manager", "error", `Failed to spawn bridge: ${err.message}`);
      return false;
    }
  }

  public async stop(): Promise<boolean> {
    if (!this.childProcess || !this.isRunning) return true;

    return new Promise((resolve) => {
      this.addLog("manager", "info", "Stopping Stratum Bridge process...");
      this.childProcess?.kill("SIGTERM");

      const timeout = setTimeout(() => {
        if (this.childProcess) {
          this.childProcess.kill("SIGKILL");
        }
        this.isRunning = false;
        resolve(true);
      }, 5000);

      this.childProcess?.once("exit", () => {
        clearTimeout(timeout);
        this.isRunning = false;
        resolve(true);
      });
    });
  }

  public async restart(): Promise<boolean> {
    await this.stop();
    return this.start();
  }
}
