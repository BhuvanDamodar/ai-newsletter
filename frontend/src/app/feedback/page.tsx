"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import {
  Sparkles,
  Loader2,
  CheckCircle2,
  ThumbsUp,
  ThumbsDown,
  AlertTriangle,
  ExternalLink,
} from "lucide-react";
import Link from "next/link";

interface VerifyData {
  valid: boolean;
  article_title: string;
  article_url: string;
  rating: number;
}

function FeedbackContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [verifyData, setVerifyData] = useState<VerifyData | null>(null);
  const [status, setStatus] = useState<
    "loading" | "verified" | "confirming" | "success" | "error" | "expired"
  >("loading");
  const [message, setMessage] = useState("");
  const [loadingMessage, setLoadingMessage] = useState("Verifying your feedback link...");

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Step 1: Verify the token (non-mutating GET)
  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("No feedback token was provided in the URL.");
      return;
    }

    const verify = async () => {
      const timer = setTimeout(() => {
        setLoadingMessage(
          "Connecting to Briefly.ai — the first request may take a few moments..."
        );
      }, 3000);

      try {
        const res = await fetch(
          `${apiUrl}/api/feedback/verify?token=${encodeURIComponent(token)}`
        );
        const data = await res.json();

        if (res.ok && data.valid) {
          setVerifyData(data);
          setStatus("verified");
        } else {
          const detail = data.detail || "Invalid feedback link.";
          if (detail.includes("expired")) {
            setStatus("expired");
            setMessage(detail);
          } else {
            setStatus("error");
            setMessage(detail);
          }
        }
      } catch (err: any) {
        setStatus("error");
        setMessage(
          err.message || "Unable to reach the server. Please try again."
        );
      } finally {
        clearTimeout(timer);
      }
    };

    verify();
  }, [token, apiUrl]);

  // Step 2: Confirm feedback (mutating POST)
  const handleConfirm = async () => {
    if (!token) return;

    setStatus("confirming");
    setLoadingMessage("Recording your feedback...");

    const timer = setTimeout(() => {
      setLoadingMessage(
        "Connecting to Briefly.ai — the first request may take a few moments..."
      );
    }, 3000);

    try {
      const res = await fetch(`${apiUrl}/api/feedback/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const data = await res.json();

      if (res.ok && data.status === "success") {
        setStatus("success");
      } else {
        setStatus("error");
        setMessage(data.detail || data.message || "Failed to record feedback.");
      }
    } catch (err: any) {
      setStatus("error");
      setMessage(
        err.message || "Unable to reach the server. Please try again."
      );
    } finally {
      clearTimeout(timer);
    }
  };

  const isLike = verifyData?.rating === 1;
  const ratingEmoji = isLike ? "👍" : "👎";
  const ratingLabel = isLike ? "Relevant" : "Not for me";
  const ratingColor = isLike ? "green" : "red";

  // ── Loading state ──
  if (status === "loading") {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md glass-card rounded-3xl p-8 flex flex-col items-center text-center space-y-4"
      >
        <Loader2 className="w-12 h-12 animate-spin text-brand-500" />
        <p className="text-text-muted text-sm animate-pulse">
          {loadingMessage}
        </p>
      </motion.div>
    );
  }

  // ── Expired token ──
  if (status === "expired") {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md glass-card rounded-3xl p-8 flex flex-col items-center text-center space-y-4"
      >
        <div className="w-16 h-16 rounded-full bg-yellow-500/20 flex items-center justify-center">
          <AlertTriangle className="w-8 h-8 text-yellow-400" />
        </div>
        <h2 className="text-2xl font-bold">Link Expired</h2>
        <p className="text-text-muted">
          This feedback link has expired after 30 days. Don&apos;t worry — you
          can still provide feedback on articles in your next digest email.
        </p>
        <Link
          href="/"
          className="mt-6 px-6 py-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
        >
          Return Home
        </Link>
      </motion.div>
    );
  }

  // ── Error state ──
  if (status === "error") {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md glass-card rounded-3xl p-8 flex flex-col items-center text-center space-y-4"
      >
        <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center">
          <AlertTriangle className="w-8 h-8 text-red-400" />
        </div>
        <h2 className="text-2xl font-bold text-red-400">
          Something Went Wrong
        </h2>
        <p className="text-red-400 bg-red-400/10 p-4 rounded-xl border border-red-400/20">
          {message}
        </p>
        <Link
          href="/"
          className="mt-4 px-6 py-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
        >
          Return Home
        </Link>
      </motion.div>
    );
  }

  // ── Success state ──
  if (status === "success") {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md glass-card rounded-3xl p-8 flex flex-col items-center text-center space-y-4"
      >
        <CheckCircle2 className="w-16 h-16 text-green-400" />
        <h2 className="text-2xl font-bold">Feedback Recorded!</h2>
        <p className="text-text-muted">
          We&apos;ve adjusted your Briefly.ai digest preferences. Your future
          digests will better reflect your interests.
        </p>
        {verifyData && (
          <a
            href={verifyData.article_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-flex items-center gap-2 text-brand-400 hover:text-brand-500 transition-colors text-sm"
          >
            Read article <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
        <Link
          href="/"
          className="mt-4 px-6 py-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
        >
          Return Home
        </Link>
      </motion.div>
    );
  }

  // ── Verified: show confirmation card (status === "verified" | "confirming") ──
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="w-full max-w-md glass-card rounded-3xl p-8 text-center"
    >
      <div className="flex justify-center mb-6">
        <div
          className={`w-16 h-16 rounded-full flex items-center justify-center ${
            isLike
              ? "bg-green-500/20 text-green-400"
              : "bg-red-500/20 text-red-400"
          }`}
        >
          {isLike ? (
            <ThumbsUp className="w-8 h-8" />
          ) : (
            <ThumbsDown className="w-8 h-8" />
          )}
        </div>
      </div>

      <h2 className="text-2xl font-bold mb-3">
        Mark as {ratingEmoji} {ratingLabel}?
      </h2>

      <div className="my-6 p-4 rounded-xl bg-white/5 border border-white/10 text-left">
        <p className="text-xs text-text-muted uppercase tracking-wider mb-1">
          Article
        </p>
        <p className="font-semibold text-base leading-snug">
          {verifyData?.article_title}
        </p>
        <a
          href={verifyData?.article_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-flex items-center gap-1.5 text-brand-400 hover:text-brand-500 text-sm transition-colors"
        >
          View article <ExternalLink className="w-3 h-3" />
        </a>
      </div>

      <button
        disabled={status === "confirming"}
        onClick={handleConfirm}
        className={`w-full px-6 py-3.5 rounded-xl font-medium transition-colors flex items-center justify-center gap-2 text-sm sm:text-base select-none disabled:opacity-50 disabled:cursor-not-allowed ${
          isLike
            ? "bg-green-500 hover:bg-green-600 text-white"
            : "bg-red-500 hover:bg-red-600 text-white"
        }`}
      >
        {status === "confirming" && (
          <Loader2 className="w-4 h-4 animate-spin" />
        )}
        {isLike ? "Confirm That This Is Relevant" : "Confirm Not For Me"}
      </button>

      {status === "confirming" && (
        <p className="text-brand-300 text-xs mt-3 flex items-center justify-center gap-1.5 animate-pulse">
          <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
          {loadingMessage}
        </p>
      )}
    </motion.div>
  );
}

export default function FeedbackPage() {
  return (
    <>
      {/* Privacy: prevent token leakage via Referer headers */}
      <meta name="referrer" content="no-referrer" />

      <main className="min-h-screen relative overflow-hidden flex flex-col items-center justify-center p-6">
        {/* Brand Logo / Navbar */}
        <div className="absolute top-6 left-6 z-20 flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-3 hover:opacity-80 transition-opacity"
          >
            <div className="w-10 h-10 rounded-xl bg-brand-500 flex items-center justify-center shadow-lg shadow-brand-500/20">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-xl tracking-tight text-white">
              briefly.ai
            </span>
          </Link>
        </div>

        {/* Background Decor */}
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-brand-600/20 rounded-full blur-[120px] pointer-events-none" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-600/20 rounded-full blur-[120px] pointer-events-none" />

        {/* Main Content */}
        <div className="z-10 w-full flex justify-center">
          <Suspense
            fallback={
              <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
            }
          >
            <FeedbackContent />
          </Suspense>
        </div>
      </main>
    </>
  );
}
