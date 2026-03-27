"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Sparkles, Mail, CheckCircle2, Loader2, BrainCircuit, Code, PenTool, LayoutTemplate, Building, Shield, Microchip, BookOpen } from "lucide-react";

export default function Home() {
  const [email, setEmail] = useState("");
  const [preferences, setPreferences] = useState<string[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");

  const topics = [
    { id: "llm", label: "LLMs & Models", icon: BrainCircuit },
    { id: "development", label: "AI Development", icon: Code },
    { id: "design", label: "AI Design", icon: PenTool },
    { id: "startups", label: "AI Startups", icon: LayoutTemplate },
    { id: "enterprise", label: "Enterprise AI", icon: Building },
    { id: "ethics", label: "Ethics & Safety", icon: Shield },
    { id: "hardware", label: "AI Hardware", icon: Microchip },
    { id: "research", label: "AI Research", icon: BookOpen },
  ];

  const handleTogglePreference = (topicId: string) => {
    setPreferences(prev => 
      prev.includes(topicId) 
        ? prev.filter(t => t !== topicId)
        : [...prev, topicId]
    );
  };

  const handleSubscribe = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;

    setStatus("loading");
    setErrorMessage("");

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, preferences }),
      });

      if (!res.ok) throw new Error("Failed to subscribe. Please try again.");
      
      setStatus("success");
    } catch (err: any) {
      setStatus("error");
      setErrorMessage(err.message || "An unexpected error occurred.");
    }
  };

  return (
    <main className="min-h-screen relative overflow-hidden flex flex-col items-center justify-center p-6">
      {/* Brand Logo / Navbar */}
      <div className="absolute top-6 left-6 md:top-8 md:left-8 z-20 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-brand-500 flex items-center justify-center shadow-lg shadow-brand-500/20">
          <Sparkles className="w-5 h-5 text-white" />
        </div>
        <span className="font-bold text-xl tracking-tight text-white">briefly.ai</span>
      </div>

      {/* Background Decor */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-brand-600/20 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-600/20 rounded-full blur-[120px] pointer-events-none" />

      <div className="max-w-4xl w-full z-10 flex flex-col items-center">
        {/* Header */}
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-12"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass mb-6">
            <Sparkles className="w-5 h-5 text-brand-400" />
            <span className="text-sm font-medium text-brand-100">AI-Curated Daily Insight</span>
          </div>
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6 leading-tight">
            Stay Ahead of the <br />
            <span className="text-gradient">AI Revolution</span>
          </h1>
          <p className="text-xl text-text-muted max-w-2xl mx-auto">
            Get a personalized, intelligent daily digest of the most important AI news, filtered exactly to your professional interests.
          </p>
        </motion.div>

        {/* Form Section */}
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="w-full max-w-xl glass-card rounded-3xl p-8"
        >
          {status === "success" ? (
            <motion.div 
              initial={{ opacity: 0 }} 
              animate={{ opacity: 1 }} 
              className="flex flex-col items-center text-center space-y-4 py-8"
            >
              <CheckCircle2 className="w-16 h-16 text-green-400" />
              <h2 className="text-2xl font-bold">You're Subscribed!</h2>
              <p className="text-text-muted">
                Welcome to Briefly AI. Your personalized intelligence feed starts tomorrow.
              </p>
              <button 
                onClick={() => setStatus("idle")}
                className="mt-6 px-6 py-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
              >
                Manage Preferences
              </button>
            </motion.div>
          ) : (
            <form onSubmit={handleSubscribe} className="space-y-8">
              <div className="space-y-4">
                <label className="block text-sm font-medium text-brand-100">
                  Select Your Interests
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {topics.map(topic => {
                    const Icon = topic.icon;
                    const isSelected = preferences.includes(topic.id);
                    return (
                      <button
                        key={topic.id}
                        type="button"
                        onClick={() => handleTogglePreference(topic.id)}
                        className={`flex items-center gap-3 p-4 rounded-xl transition-all border outline-none ${
                          isSelected 
                            ? "bg-brand-500/20 border-brand-500 text-white" 
                            : "bg-white/5 border-white/10 text-text-muted hover:bg-white/10"
                        }`}
                      >
                        <Icon className={`w-5 h-5 ${isSelected ? "text-brand-400" : ""}`} />
                        <span className="font-medium">{topic.label}</span>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="space-y-4">
                <label htmlFor="email" className="block text-sm font-medium text-brand-100">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                  <input 
                    id="email"
                    type="email" 
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="hello@example.com"
                    className="w-full pl-12 pr-4 py-4 bg-white/5 border border-white/10 rounded-xl outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-all placeholder:text-text-muted/50"
                  />
                  <button 
                    disabled={status === "loading" || !email}
                    type="submit"
                    className="absolute right-2 top-1/2 -translate-y-1/2 px-6 py-2.5 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 disabled:hover:bg-brand-600 rounded-lg font-medium transition-colors flex items-center gap-2"
                  >
                    {status === "loading" && <Loader2 className="w-4 h-4 animate-spin" />}
                    Subscribe
                  </button>
                </div>
                {status === "error" && (
                  <p className="text-red-400 text-sm mt-2">{errorMessage}</p>
                )}
              </div>
            </form>
          )}
        </motion.div>
      </div>
    </main>
  );
}
