#!/usr/bin/env node
/**
 * FREE, no-gas pre-deploy check: client.getContractSchemaForCode(code)
 * fails instantly and deterministically if the network can't resolve
 * this contract's runner/Depends hash right now -- confirmed cheaper
 * and faster than finding out via a real, gas-costing deploy attempt.
 * Run this BEFORE any real deployContract() call, for both a minimal
 * probe contract and the real bundle.
 *
 * Usage: node deploy/probe_schema.mjs <path-to-contract.py>
 */
import { createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
import { readFileSync } from "node:fs";

const path = process.argv[2];
if (!path) {
  console.error("usage: node deploy/probe_schema.mjs <path-to-contract.py>");
  process.exit(1);
}

const code = readFileSync(path, "utf-8");
const client = createClient({ chain: studioDevnet });

console.log(`Probing getContractSchemaForCode for ${path} (${code.length} bytes)...`);
try {
  const schema = await client.getContractSchemaForCode(code);
  console.log("OK -- schema resolved:");
  console.log(JSON.stringify(schema, null, 2));
} catch (err) {
  console.error("FAILED:", err?.message ?? err);
  process.exit(1);
}
