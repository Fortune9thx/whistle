export function formatGen(wei: string | number | bigint, decimals = 4): string {
  const v = typeof wei === "bigint" ? wei : BigInt(Math.trunc(Number(wei)));
  const scale = 10n ** 18n;
  const whole = v / scale;
  const frac = v % scale;
  const fracStr = frac.toString().padStart(18, "0").slice(0, decimals);
  const trimmed = fracStr.replace(/0+$/, "");
  return trimmed ? `${whole}.${trimmed}` : whole.toString();
}

export function genToWei(gen: string): bigint {
  const [whole, frac = ""] = gen.trim().split(".");
  const fracPadded = (frac + "0".repeat(18)).slice(0, 18);
  return BigInt(whole || "0") * 10n ** 18n + BigInt(fracPadded || "0");
}

export function shortAddr(addr: string | null | undefined): string {
  if (!addr) return "";
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

export function formatKickoff(unix: number): string {
  return new Date(unix * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function timeUntil(unix: number): string {
  const diff = unix * 1000 - Date.now();
  if (diff <= 0) return "now";
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ${mins % 60}m`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}
