import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, Send, Sparkles, Tag, AlertCircle } from "lucide-react";
import { AppState, ChatMessage, LostItemProfile } from "../types";
import { generateDetectiveResponse } from "../services/geminiService";
import { Button } from "./ui/Button";

interface LostFlowProps {
  setAppState: (state: AppState) => void;
}

export const LostFlow: React.FC<LostFlowProps> = ({ setAppState }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "intro",
      sender: "ai",
      text: "Detective Sherlock here. I'm sorry to hear something's gone missing. Let's trace your steps. What is it that you've lost?",
      timestamp: Date.now(),
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(false);
  const [finalDescription, setFinalDescription] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [showEmailPrompt, setShowEmailPrompt] = useState(false);
  const [displayProbability, setDisplayProbability] = useState(10);
  const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
  const handleFinalize = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${baseUrl}/api/detective/finalize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          history: messages.map((m) => ({
            role: m.sender === "user" ? "user" : "assistant",
            content: m.text,
          })),
        }),
      });

      const data = await res.json();
      setFinalDescription(data.final_description);
      if (data.recovery_probability !== undefined) {
        setProfile((prev) => ({ ...prev, confidence: data.recovery_probability }));
      }
    } catch (error) {
      console.error("Finalize Error:", error);
    }
    setLoading(false);
  };
  

  // Profile State
  const [profile, setProfile] = useState<LostItemProfile>({
    category: "Unknown",
    confidence: 10,
    tags: [],
    colorHex: "#cccccc",
    lastSeen: "Unknown",
    time: "12:00",
    days_since_loss: 0
  });
  useEffect(() => {
    if (!profile) return;

    const clues = [
      profile.category,
      profile.color,
      profile.location,
      profile.time
    ].filter(v => v && v !== "Unknown").length;

    // base probability grows as clues increase
    const baseProbability = 20 + clues * 15;

    // random ML-like noise
    const randomShift = Math.floor(Math.random() * 10) - 5;

    let newProb = baseProbability + randomShift;

    // clamp limits
    newProb = Math.max(10, Math.min(95, newProb));

    setDisplayProbability(newProb);

  }, [profile]);
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: "user",
      text: inputValue,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputValue("");
    setIsThinking(true);

    // AI Processing
    const history = messages.map((m) => ({
      role: m.sender === "ai" ? "assistant" : "user",
      content: m.text,
    }));

    const response = await generateDetectiveResponse(history, userMsg.text, {
      category: profile.category,
      color: profile.colorHex, // simplified mapping
      location: profile.lastSeen,
      time: profile.time || "12:00",
      days_since_loss: profile.days_since_loss || 0
    });

    setIsThinking(false);

    // Update AI Message
    const aiMsg: ChatMessage = {
      id: (Date.now() + 1).toString(),
      sender: "ai",
      text: response.text,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, aiMsg]);

    // Update Profile visuals
    setProfile((prev) => {
      const newConfidence = response.recovery_probability;
      const newCategory = response.current_category && response.current_category !== "Unknown" ? response.current_category : prev.category;
      const newLocation = response.current_location && response.current_location !== "Unknown" ? response.current_location : prev.lastSeen;
      const newTime = response.current_time && response.current_time !== "Unknown" ? response.current_time : prev.time;
      const newDays = response.current_days !== undefined && response.current_days !== null ? response.current_days : prev.days_since_loss;
      const newColor = response.current_color && response.current_color !== "Unknown" ? response.current_color : prev.colorHex;

      return {
        ...prev,
        confidence: newConfidence,
        tags: [...new Set([...prev.tags, ...response.tags])],
        category: newCategory,
        lastSeen: newLocation,
        time: newTime,
        days_since_loss: newDays,
        colorHex: newColor
      };
    });
  };
  const handleSubmitLost = async () => {
    if (!finalDescription || !email) {
      alert("Please provide both a description and an email.");
      return;
    }

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("description", finalDescription);
      formData.append("email", email);
      formData.append("category", profile.category);
      formData.append("color", profile.colorHex);
      formData.append("location", profile.lastSeen);
      formData.append("time", profile.time || "12:00");
      formData.append("days_since_loss", (profile.days_since_loss || 0).toString());

      const res = await fetch(`${baseUrl}/lost/`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (data.success) {
        setProfile((prev) => ({
          ...prev,
          generatedImage: data.image_url,
          // Removed hardcoded confidence: 100 to keep the model's prediction
        }));

        if (data.match_found) {
          alert("Detective Sherlock found a potential match! Check your email.");
        } else {
          alert("Case successfully filed. We'll notify you if a match is found.");
        }

        setShowEmailPrompt(false);
      } else {
        alert(" Something went wrong: " + data.message);
      }
    } catch (error) {
      console.error("Submit Lost Error:", error);
      alert(" Server error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full h-screen flex flex-col md:flex-row bg-[#f4f1ea] relative overflow-hidden">
      {/* LEFT: The Detective's Desk (Chat) */}
      <div className="w-full md:w-1/2 h-full flex flex-col p-4 md:p-8 border-r-2 border-[#2d2d2d] relative z-10">
        <div className="mb-6 flex items-center justify-between">
          <button
            onClick={() => setAppState(AppState.LANDING)}
            className="flex items-center text-[#2d2d2d] hover:underline font-bold"
          >
            <ArrowLeft size={20} className="mr-2" />
            Case Files
          </button>
          <div className="bg-[#2d2d2d] text-[#f4f1ea] px-3 py-1 rounded-sm font-display text-xs tracking-widest uppercase">
            Active Investigation
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto pr-2 space-y-6">
          {messages.map((msg) => (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              key={msg.id}
              className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] p-4 paper-shadow-sm border border-[#2d2d2d] relative ${msg.sender === "user"
                  ? "bg-[#e07a5f] text-white rotate-1 rounded-tl-xl rounded-br-xl rounded-bl-xl"
                  : "bg-white text-[#2d2d2d] -rotate-1 rounded-tr-xl rounded-br-xl rounded-bl-xl"
                  }`}
              >
                {msg.sender === "ai" && (
                  <div className="absolute -top-3 -left-3 bg-[#2d2d2d] text-white p-1 rounded-full border border-white">
                    <Sparkles size={12} />
                  </div>
                )}
                <p className="font-hand text-lg leading-relaxed">{msg.text}</p>
              </div>
            </motion.div>
          ))}
          {isThinking && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-start"
            >
              <div className="bg-[#f0f0f0] p-3 rounded-lg flex space-x-2 items-center">
                <div
                  className="w-2 h-2 bg-[#2d2d2d] rounded-full animate-bounce"
                  style={{ animationDelay: "0s" }}
                ></div>
                <div
                  className="w-2 h-2 bg-[#2d2d2d] rounded-full animate-bounce"
                  style={{ animationDelay: "0.2s" }}
                ></div>
                <div
                  className="w-2 h-2 bg-[#2d2d2d] rounded-full animate-bounce"
                  style={{ animationDelay: "0.4s" }}
                ></div>
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} />
        </div>
        {/* Finalize Button */}
        {messages.filter((m) => m.sender === "user").length >= 2 &&
          !finalDescription && (
            <div className="mt-4 flex justify-center">
              <button
                onClick={handleFinalize}
                className="bg-[#2d2d2d] text-[#f4f1ea] px-6 py-2 tracking-widest uppercase text-xs border border-[#2d2d2d] hover:bg-[#e07a5f] hover:border-[#e07a5f] transition-all"
              >
                Finalize Case File
              </button>
            </div>
          )}

        {finalDescription && !showEmailPrompt && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-4 border border-[#2d2d2d] p-4 bg-[#f4f1ea]"
          >
            <h3 className="font-display uppercase tracking-widest text-xs mb-2">
              Final Case Description
            </h3>

            <textarea
              value={finalDescription}
              onChange={(e) => setFinalDescription(e.target.value)}
              className="w-full p-3 border border-[#2d2d2d] bg-white font-hand text-lg focus:outline-none"
              rows={4}
            />
            <div className="flex justify-between mt-3">
              <button
                onClick={() => setFinalDescription(null)}
                className="text-sm underline"
              >
                Edit Investigation
              </button>

              <button
                onClick={() => setShowEmailPrompt(true)}
                className="bg-[#e07a5f] text-white px-5 py-2 uppercase text-xs tracking-widest hover:bg-[#d65f44]"
              >
                Next Step: Contact Info
              </button>
            </div>
          </motion.div>
        )}

        {showEmailPrompt && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mt-4 border-2 border-[#e07a5f] p-6 bg-white rotate-1"
          >
            <h3 className="font-display uppercase tracking-widest text-sm mb-4 font-bold border-b border-[#2d2d2d] pb-2">
              Where should we send updates?
            </h3>
            <div className="space-y-4">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email address"
                className="w-full p-3 border border-[#2d2d2d] font-hand text-lg"
                autoFocus
              />
              <div className="flex justify-between">
                <button
                  onClick={() => setShowEmailPrompt(false)}
                  className="text-sm underline"
                >
                  Back
                </button>
                <button
                  onClick={handleSubmitLost}
                  disabled={loading || !email}
                  className="bg-[#2d2d2d] text-white px-6 py-2 uppercase text-xs tracking-widest disabled:opacity-50"
                >
                  {loading ? "Filing Case..." : "File Final Report"}
                </button>
              </div>
            </div>
          </motion.div>
        )}

        {/* Input Area */}
        <div className="mt-6 relative">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
            placeholder="Type your answer..."
            className="w-full bg-transparent border-b-2 border-[#2d2d2d] p-4 pr-12 font-display text-xl focus:outline-none focus:border-[#e07a5f] transition-colors"
            autoFocus
          />
          <button
            onClick={handleSendMessage}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-[#2d2d2d] hover:text-[#e07a5f] transition-colors"
          >
            <Send size={24} />
          </button>
        </div>
      </div>

      {/* RIGHT: The Evidence Board (Dynamic Profile) */}
      <div className="w-full md:w-1/2 h-full bg-[#e8e4db] p-8 relative overflow-hidden">
        {/* Background pattern for the board */}
        <div
          className="absolute inset-0 opacity-5 pointer-events-none"
          style={{
            backgroundImage: "radial-gradient(#2d2d2d 1px, transparent 1px)",
            backgroundSize: "20px 20px",
          }}
        ></div>

        <div className="max-w-md mx-auto h-full flex flex-col justify-center space-y-8 relative z-10">
          {/* Header */}
          <div className="text-center">
            <h3 className="font-display font-bold text-2xl uppercase tracking-widest mb-2 border-b-4 border-[#2d2d2d] inline-block pb-1">
              Subject Profile
            </h3>
          </div>

          {/* Visualizer Frame */}
          <motion.div
            className="w-full aspect-square bg-white paper-shadow border-2 border-[#2d2d2d] p-4 relative flex items-center justify-center overflow-hidden group"
            layout
          >
            <div
              className="absolute top-2 left-1/2 -translate-x-1/2 w-24 h-6 bg-[#d4c5a3] opacity-80 z-20 shadow-sm"
              style={{ transform: "rotate(-2deg)" }}
            ></div>{" "}
            {/* Tape */}
            {/* The "Generated" Sketch Area */}
            <div className="w-full h-full border border-dashed border-gray-300 rounded-sm flex items-center justify-center relative">
              {profile.tags.length === 0 ? (
                <span className="font-hand text-gray-400 text-2xl -rotate-6">
                  Awaiting details...
                </span>
              ) : (
                <div className="relative w-3/4 h-3/4">
                  {/* Abstract representation of the item based on tags */}
                  {profile.generatedImage ? (
                    <motion.img
                      src={profile.generatedImage}
                      alt="Generated Lost Item"
                      className="w-full h-full object-contain rounded-lg border-2 border-[#2d2d2d]"
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: 0.4 }}
                    />
                  ) : (
                    <motion.div
                      className="w-full h-full bg-[#f0f0f0] rounded-lg border-2 border-[#2d2d2d] flex items-center justify-center"
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                    >
                      <span className="font-display font-bold text-4xl text-[#2d2d2d] opacity-20 uppercase">
                        {profile.tags[0] || "?"}
                      </span>
                    </motion.div>
                  )}

                  {/* Stickers for tags */}
                  {profile.tags.map((tag, i) => (
                    <motion.div
                      key={tag}
                      initial={{ scale: 0, rotate: 0 }}
                      animate={{
                        scale: 1,
                        rotate: (i % 2 === 0 ? 10 : -10) + i * 5,
                      }}
                      className="absolute bg-[#e07a5f] text-white px-2 py-1 font-bold font-hand text-sm border border-[#2d2d2d] paper-shadow-sm"
                      style={{
                        top: `${20 + i * 15}%`,
                        right: `${-10 + i * 5}%`,
                        zIndex: 10 + i,
                      }}
                    >
                      {tag}
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>

          {/* Stats & Confidence */}
          <div className="space-y-4">
            <div className="flex justify-between items-end">
              <span className="font-display font-bold text-lg">
                Recovery Probability
              </span>
              <span className="font-display font-bold text-3xl text-[#e07a5f]">
                {displayProbability}%
              </span>
            </div>

            {/* Custom Progress Bar */}
            <div className="w-full h-6 border-2 border-[#2d2d2d] p-1 bg-white rounded-full">
              <motion.div
                className="h-full bg-gradient-to-r from-[#81b29a] to-[#e07a5f] rounded-full border border-[#2d2d2d]"
                initial={{ width: "10%" }}
                animate={{ width: `${displayProbability}%` }}
                transition={{ duration: 0.8 }}
              />
            </div>

            <div className="flex flex-wrap gap-2 pt-2">
              <span className="flex items-center text-sm font-bold text-[#2d2d2d]">
                <Tag size={16} className="mr-1" />
                Identified Traits:
              </span>
              {profile.tags.length === 0 && (
                <span className="text-gray-400 font-hand text-sm">
                  None yet
                </span>
              )}
              {profile.tags.map((tag) => (
                <span
                  key={tag}
                  className="bg-[#f4f1ea] border border-[#2d2d2d] px-2 py-0.5 text-xs font-mono rounded-sm"
                >
                  #{tag}
                </span>
              ))}
            </div>
          </div>

          {/* Action */}
          {profile.confidence > 60 && (
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
            >
              <Button
                className="w-full"
                onClick={() => setAppState(AppState.VERIFICATION)}
              >
                Match Found in Archive
              </Button>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
};
