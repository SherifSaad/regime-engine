"use client";

import Link from "next/link";
import { useRef, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Turnstile } from "@/components/auth/Turnstile";
import LegalAcceptanceBlock, { type LegalAcceptanceBlockRef } from "@/components/legal/LegalAcceptanceBlock";

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [legalValid, setLegalValid] = useState(false);
  const legalRef = useRef<LegalAcceptanceBlockRef>(null);
  // IMPORTANT: Placeholder until auth exists. As soon as you have a real user_id from your
  // create-user flow, pass it into LegalAcceptanceBlock instead, OR after creating the user
  // call POST /api/legal/accept (terms + privacy) and POST /api/consent/email (if marketing)
  // again with the real user_id so acceptance is tied to the actual account.
  const tempUserId = useMemo(() => "tmp_" + Date.now(), []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!legalValid) {
      setError("Please agree to the Terms of Service and Privacy Policy.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (TURNSTILE_SITE_KEY && !turnstileToken) {
      setError("Please complete the security check.");
      return;
    }
    setLoading(true);
    try {
      const recorded = await legalRef.current?.record();
      if (!recorded) {
        setError("Could not record legal acceptance. Please try again.");
        setLoading(false);
        return;
      }
      // TODO: wire to auth backend (NextAuth/Clerk/Supabase) + email verification
      // When you create the user, either pass the new user_id into LegalAcceptanceBlock next
      // time, or re-post acceptance with real user_id: POST /api/legal/accept (terms + privacy)
      // and POST /api/consent/email (if marketing) so records are tied to the real account.
      // await fetch("/api/auth/signup", { method: "POST", body: JSON.stringify({ email, password, turnstileToken }) });
      console.log("Signup (auth not connected):", { email, hasTurnstile: !!turnstileToken });
      setError("Sign-up is not yet connected. Add your auth provider and email verification.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-sm px-6 py-16">
      <h1 className="text-2xl font-bold tracking-tight">Sign up</h1>
      <p className="mt-2 text-sm text-zinc-600">
        Free. No credit card required. We’ll send a verification link to your email.
      </p>

      <form onSubmit={handleSubmit} className="mt-8 space-y-4">
        <div className="space-y-2">
          <Label htmlFor="signup-email">Email</Label>
          <Input
            id="signup-email"
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
          <Label htmlFor="signup-password">Password</Label>
          <Input
            id="signup-password"
            type="password"
            autoComplete="new-password"
            placeholder="At least 8 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            className="w-full"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="signup-confirm">Confirm password</Label>
          <Input
            id="signup-confirm"
            type="password"
            autoComplete="new-password"
            placeholder="Repeat password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            className="w-full"
          />
        </div>

        {TURNSTILE_SITE_KEY ? (
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

        <div style={{ marginTop: 12 }}>
          <LegalAcceptanceBlock
            ref={legalRef}
            userId={tempUserId}
            email={email || null}
            source="signup"
            onValidityChange={setLegalValid}
          />
        </div>

        {error ? <p className="text-sm text-red-600">{error}</p> : null}

        <Button type="submit" className="w-full" disabled={loading || !legalValid}>
          {loading ? "Creating account…" : "Sign up"}
        </Button>

        <div className="relative my-6">
          <span className="absolute inset-0 flex items-center">
            <span className="w-full border-t border-zinc-200" />
          </span>
          <span className="relative flex justify-center text-xs text-zinc-500">Or continue with</span>
        </div>
        <Button type="button" variant="outline" className="w-full" asChild>
          <a href="/api/auth/signin/google">
            {/* TODO: replace with your OAuth sign-in URL (NextAuth/Clerk/etc.) */}
            Sign up with Google
          </a>
        </Button>
      </form>

      <p className="mt-6 text-center text-xs text-zinc-500">
        By signing up, you agree to our{" "}
        <Link href="/legal/terms" className="underline hover:text-zinc-700">Terms of Service</Link>
        {" "}and{" "}
        <Link href="/legal/privacy" className="underline hover:text-zinc-700">Privacy Policy</Link>.
      </p>
      <p className="mt-4 text-center text-sm text-zinc-500">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-zinc-900 hover:underline">
          Log in
        </Link>
      </p>
    </div>
  );
}
