export interface CloudflareEnv {
  DB: D1Database;
  NODE_ENV: string;
}

export interface D1Result<T = any> {
  results: T[];
  success: boolean;
  meta: {
    duration: number;
    size_after: number;
    rows_read: number;
    rows_written: number;
  };
}

export interface D1PreparedStatement {
  bind(...values: any[]): D1PreparedStatement;
  first<T = any>(): Promise<T | null>;
  all<T = any>(): Promise<D1Result<T>>;
  run(): Promise<D1Result>;
}

export interface D1Database {
  prepare(sql: string): D1PreparedStatement;
  exec(sql: string): Promise<D1Result>;
}

declare global {
  namespace App {
    interface Locals {
      runtime: {
        env: CloudflareEnv;
      };
    }
  }
}