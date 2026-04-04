"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { Sparkles, Loader2, CheckCircle2, UserMinus } from "lucide-react";
import Link from "next/link";

function UnsubscribeContent() {
  const searchParams = useSearchParams();
  const email = searchParams.get("email");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  const handleUnsubscribe = () => {
    if (!email) return;
    
    // Instantly show success so the user doesn't have to wait for Render to wake up
    setStatus("success");
    
    // Fire the API request in the background
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      fetch(`${apiUrl}/api/unsubscribe?email=${encodeURIComponent(email)}`).catch(err => {
        console.error("Background unsubscribe failed:", err);
      });
    } catch (err) {
      console.error("Failed to initiate unsubscribe:", err);
    }
  };

  if (!email) {
    return (
      <div className="w-full max-w-md glass-card rounded-3xl p-8 text-center">
        <h2 className="text-2xl font-bold mb-4 text-red-400">Invalid Link</h2>
        <p className="text-text-muted">No email address was provided in the URL to unsubscribe.</p>
        <Link href="/" className="mt-8 inline-block px-6 py-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors">
          Return Home
        </Link>
      </div>
    );
  }

  if (status === "success") {
    return (
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md glass-card rounded-3xl p-8 flex flex-col items-center text-center space-y-4"
      >
        <CheckCircle2 className="w-16 h-16 text-green-400" />
        <h2 className="text-2xl font-bold">Unsubscribed Successfully</h2>
        <p className="text-text-muted">
          <b>{email}</b> has been removed from our mailing list. You will no longer receive daily AI news digests.
        </p>
        <Link href="/" className="mt-6 px-6 py-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors">
          Return Home
        </Link>
      </motion.div>
    );
  }

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="w-full max-w-md glass-card rounded-3xl p-8 text-center"
    >
      <div className="flex justify-center mb-6">
        <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center text-red-400">
          <UserMinus className="w-8 h-8" />
        </div>
      </div>
      <h2 className="text-2xl font-bold mb-4">Unsubscribe</h2>
      
      {status === "error" ? (
        <div className="space-y-6">
          <p className="text-red-400 bg-red-400/10 p-4 rounded-xl border border-red-400/20">
            {message}
          </p>
          <Link href="/" className="inline-block px-6 py-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors">
            Return Home
          </Link>
        </div>
      ) : (
        <div className="space-y-8">
          <p className="text-text-muted">
            Are you sure you want to stop receiving your daily AI-curated insight for <strong>{email}</strong>?
          </p>
          <button
            disabled={status === "loading"}
            onClick={handleUnsubscribe}
            className="w-full px-6 py-3.5 bg-red-500 hover:bg-red-600 disabled:opacity-50 rounded-xl font-medium transition-colors flex items-center justify-center gap-2 text-white"
          >
            {status === "loading" && <Loader2 className="w-4 h-4 animate-spin" />}
            Confirm Unsubscribe
          </button>
        </div>
      )}
    </motion.div>
  );
}

export default function UnsubscribePage() {
  return (
    <main className="min-h-screen relative overflow-hidden flex flex-col items-center justify-center p-6">
      {/* Brand Logo / Navbar */}
      <div className="absolute top-6 left-6 z-20 flex items-center gap-3">
        <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
          <div className="w-10 h-10 rounded-xl bg-brand-500 flex items-center justify-center shadow-lg shadow-brand-500/20">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <span className="font-bold text-xl tracking-tight text-white">briefly.ai</span>
        </Link>
      </div>

      {/* Background Decor */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-brand-600/20 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-600/20 rounded-full blur-[120px] pointer-events-none" />

      {/* Main Content */}
      <div className="z-10 w-full flex justify-center">
        <Suspense fallback={<Loader2 className="w-8 h-8 animate-spin text-brand-500" />}>
          <UnsubscribeContent />
        </Suspense>
      </div>
    </main>
  );
}
