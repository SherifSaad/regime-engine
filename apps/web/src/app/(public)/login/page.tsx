"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Turnstile } from "@/components/auth/Turnstile";

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";
// Set to "1" or "true" when you want to show Turnstile on login (e.g. risk-based or random server decision).
const SHOW_TURNSTILE_ON_LOGIN = process.env.NEXT_PUBLIC_TURNSTILE_SHOW_ON_LOGIN === "1" || process.env.NEXT_PUBLIC_TURNSTILE_SHOW_ON_LOGIN === "true";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (SHOW_TURNSTILE_ON_LOGIN && TURNSTILE_SITE_KEY && !turnstileToken) {
      setError("Please complete the security check.");
      return;
    }
    setLoading(true);
    try {
      // TODO: wire to auth backend (NextAuth/Clerk/Supabase)
      // await fetch("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password, turnstileToken }) });
      console.log("Login (auth not connected):", { email, hasTurnstile: !!turnstileToken });
      setError("Log-in is not yet connected. Add your auth provider.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-sm px-6 py-16">
      <h1 className="text-2xl font-bold tracking-tight">Log in</h1>
      <p className="mt-2 text-sm text-zinc-600">
        Sign in to your account. We may occasionally ask you to complete a quick security check.
      </p>

      <form onSubmit={handleSubmit} className="mt-8 space-y-4">
        <div className="space-y-2">
          <Label htmlFor="login-email">Email</Label>
          <Input
            id="login-email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="login-password">Password</Label>
          <Input
            id="login-password"
            type="password"
            autoComplete="current-password"
            placeholder="Your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full"
          />
        </div>

        {SHOW_TURNSTILE_ON_LOGIN && TURNSTILE_SITE_KEY ? (
          <div className="flex justify-center">
            <Turnstile
              siteKey={TURNSTILE_SITE_KEY}
              onVerify={setTurnstileToken}
              onExpire={() => setTurnstileToken(null)}
              onError={() => setTurnstileToken(null)}
              theme="light"
              size="normal"
            />
          </div>
        ) : null}

        {error ? <p className="text-sm text-red-600">{error}</p> : null}

        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Signing in…" : "Log in"}
        </Button>

        <div className="relative my-6">
          <span className="absolute inset-0 flex items-center">
            <span className="w-full border-t border-zinc-200" />
          </span>
          <span className="relative flex justify-center text-xs text-zinc-500">Or continue with</span>
        </div>
        <Button type="button" variant="outline" className="w-full" asChild>
          <a href="/api/auth/signin/google">
            Log in with Google
          </a>
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-zinc-500">
        Don&apos;t have an account?{" "}
        <Link href="/signup" className="font-medium text-zinc-900 hover:underline">
          Sign up
        </Link>
      </p>
    </div>
  );
}
