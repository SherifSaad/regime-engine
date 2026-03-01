"use client";

import Script from "next/script";
import React from "react";

const TURNSTILE_SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js";

type TurnstileProps = {
  siteKey: string;
  onVerify?: (token: string) => void;
  onError?: () => void;
  onExpire?: () => void;
  theme?: "light" | "dark" | "auto";
  size?: "normal" | "compact";
  className?: string;
};

const CALLBACK_NAME = "__turnstileVerify";

export function Turnstile({
  siteKey,
  onVerify,
  onError,
  onExpire,
  theme = "light",
  size = "normal",
  className = "",
}: TurnstileProps) {
  React.useEffect(() => {
    const w = window as Window & { [key: string]: ((token: string) => void) | (() => void) | undefined };
    w[CALLBACK_NAME] = (token: string) => onVerify?.(token);
    w[`${CALLBACK_NAME}Error`] = () => onError?.();
    w[`${CALLBACK_NAME}Expire`] = () => onExpire?.();
    return () => {
      delete w[CALLBACK_NAME];
      delete w[`${CALLBACK_NAME}Error`];
      delete w[`${CALLBACK_NAME}Expire`];
    };
  }, [onVerify, onError, onExpire]);

  return (
    <>
      <Script src={TURNSTILE_SCRIPT} strategy="lazyOnload" />
      <div
        className={["cf-turnstile", className].filter(Boolean).join(" ")}
        data-sitekey={siteKey}
        data-theme={theme}
        data-size={size}
        data-callback={CALLBACK_NAME}
        data-error-callback={`${CALLBACK_NAME}Error`}
        data-expired-callback={`${CALLBACK_NAME}Expire`}
      />
    </>
  );
}
