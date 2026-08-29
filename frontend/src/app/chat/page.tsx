"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  Loader2,
  ExternalLink,
  MessageSquare,
  Sparkles,
  Bot,
  User,
  Tag,
} from "lucide-react";
import Navbar from "../components/Navbar";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ChatSource {
  id: number;
  title: string;
  url: string;
  published_at: string | null;
  key_takeaway: string | null;
  tags: string[] | null;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  loading?: boolean;
}

const suggestedQuestions = [
  "What are the latest breakthroughs in LLMs?",
  "Summarize recent OpenAI news",
  "What's happening in AI safety and ethics?",
  "Any new developments in AI hardware?",
  "What are the trending topics in machine learning research?",
  "Tell me about recent AI startup news",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async (query: string) => {
    if (!query.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: query,
    };

    const loadingMessage: ChatMessage = {
      id: (Date.now() + 1).toString(),
      role: "assistant",
      content: "",
      loading: true,
    };

    setMessages((prev) => [...prev, userMessage, loadingMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!res.ok) throw new Error("Chat request failed");

      const data = await res.json();

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === loadingMessage.id
            ? {
                ...msg,
                content: data.answer,
                sources: data.sources,
                loading: false,
              }
            : msg
        )
      );
    } catch (err) {
      console.error("Chat error:", err);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === loadingMessage.id
            ? {
                ...msg,
                content:
                  "Sorry, I encountered an error. The backend may be waking up from a cold start — please try again in a moment.",
                loading: false,
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  };

  return (
    <>
      <Navbar />
      <main className="min-h-screen pt-16 flex flex-col">
        {/* Background Decor */}
        <div className="fixed top-[-10%] right-[-5%] w-[25%] h-[25%] bg-brand-600/10 rounded-full blur-[120px] pointer-events-none" />
        <div className="fixed bottom-[-10%] left-[-5%] w-[25%] h-[25%] bg-purple-600/10 rounded-full blur-[120px] pointer-events-none" />

        {/* Chat Area */}
        <div className="flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 flex flex-col">
          {/* Empty State */}
          {messages.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center py-12">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-center mb-10"
              >
                <div className="w-16 h-16 rounded-2xl bg-brand-500/20 flex items-center justify-center mx-auto mb-5">
                  <MessageSquare className="w-8 h-8 text-brand-400" />
                </div>
                <h1 className="text-3xl sm:text-4xl font-bold tracking-tight mb-3">
                  Chat with your{" "}
                  <span className="text-gradient">News Feed</span>
                </h1>
                <p className="text-text-muted text-lg max-w-md mx-auto">
                  Ask questions about AI news from our curated archive. Powered
                  by RAG with Gemini.
                </p>
              </motion.div>

              {/* Suggested Questions */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl w-full"
              >
                {suggestedQuestions.map((question, i) => (
                  <button
                    key={i}
                    onClick={() => sendMessage(question)}
                    className="text-left p-4 rounded-xl bg-white/5 border border-white/10 text-sm text-text-muted hover:bg-white/10 hover:text-white hover:border-white/20 transition-all"
                  >
                    <Sparkles className="w-4 h-4 text-brand-400 mb-2" />
                    {question}
                  </button>
                ))}
              </motion.div>
            </div>
          ) : (
            /* Messages List */
            <div className="flex-1 overflow-y-auto py-6 space-y-6">
              <AnimatePresence>
                {messages.map((msg) => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`flex gap-3 ${
                      msg.role === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    {msg.role === "assistant" && (
                      <div className="shrink-0 w-8 h-8 rounded-lg bg-brand-500/20 flex items-center justify-center mt-1">
                        <Bot className="w-4 h-4 text-brand-400" />
                      </div>
                    )}

                    <div
                      className={`max-w-[85%] sm:max-w-[75%] ${
                        msg.role === "user"
                          ? "bg-brand-600/30 border-brand-500/30"
                          : "bg-white/5 border-white/10"
                      } border rounded-2xl px-5 py-4`}
                    >
                      {msg.loading ? (
                        <div className="flex items-center gap-2 text-text-muted">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span className="text-sm">
                            Searching articles and generating answer...
                          </span>
                        </div>
                      ) : (
                        <>
                          {/* Message Content */}
                          <div className="text-sm sm:text-base leading-relaxed whitespace-pre-wrap">
                            {msg.content}
                          </div>

                          {/* Source Citations */}
                          {msg.sources && msg.sources.length > 0 && (
                            <div className="mt-4 pt-4 border-t border-white/10">
                              <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-3">
                                Sources Referenced
                              </p>
                              <div className="space-y-2.5">
                                {msg.sources.map((source, idx) => (
                                  <a
                                    key={source.id}
                                    href={source.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-start gap-3 p-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/5 transition-all group"
                                  >
                                    <span className="shrink-0 w-6 h-6 rounded-md bg-brand-500/20 flex items-center justify-center text-xs font-bold text-brand-400 mt-0.5">
                                      {idx + 1}
                                    </span>
                                    <div className="min-w-0 flex-1">
                                      <p className="text-sm font-medium leading-snug group-hover:text-brand-100 transition-colors line-clamp-1">
                                        {source.title}
                                      </p>
                                      {source.key_takeaway && (
                                        <p className="text-xs text-text-muted mt-1 line-clamp-1">
                                          {source.key_takeaway}
                                        </p>
                                      )}
                                      <div className="flex items-center gap-2 mt-1.5">
                                        {source.published_at && (
                                          <span className="text-xs text-text-muted/60">
                                            {formatDate(source.published_at)}
                                          </span>
                                        )}
                                        {source.tags &&
                                          source.tags.slice(0, 2).map((tag) => (
                                            <span
                                              key={tag}
                                              className="text-xs px-1.5 py-0.5 rounded bg-white/5 text-text-muted/60"
                                            >
                                              {tag}
                                            </span>
                                          ))}
                                      </div>
                                    </div>
                                    <ExternalLink className="w-4 h-4 text-text-muted/40 group-hover:text-brand-400 transition-colors shrink-0 mt-1" />
                                  </a>
                                ))}
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>

                    {msg.role === "user" && (
                      <div className="shrink-0 w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center mt-1">
                        <User className="w-4 h-4 text-text-muted" />
                      </div>
                    )}
                  </motion.div>
                ))}
              </AnimatePresence>
              <div ref={messagesEndRef} />
            </div>
          )}

          {/* Input Bar */}
          <div className="sticky bottom-0 py-4 bg-gradient-to-t from-background-dark via-background-dark to-transparent">
            <form
              onSubmit={handleSubmit}
              className="max-w-4xl mx-auto relative"
            >
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about AI news..."
                disabled={isLoading}
                className="w-full pl-5 pr-14 py-4 bg-white/5 border border-white/10 rounded-2xl outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-all placeholder:text-text-muted/50 text-sm sm:text-base disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 disabled:opacity-30 disabled:hover:bg-brand-600 transition-all"
              >
                {isLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
              </button>
            </form>
          </div>
        </div>
      </main>
    </>
  );
}
