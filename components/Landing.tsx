import React from 'react';
import { motion } from 'framer-motion';
import { Search, MapPin, Watch, Umbrella, Wallet, Key, Loader2, Calendar } from 'lucide-react';
import { AppState, FoundItem } from '../types';
import { useEffect, useState } from 'react';
import { Button } from './ui/Button';

interface LandingProps {
  setAppState: (state: AppState) => void;
}

export const Landing: React.FC<LandingProps> = ({ setAppState }) => {
  const [foundItems, setFoundItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
  useEffect(() => {
    const fetchItems = async () => {
      try {
        const res = await fetch(`${baseUrl}/found-items`);
        const data = await res.json();
        console.log("FOUND ITEMS:", data);

        setFoundItems(data);
      } catch (err) {
        console.error("Failed to fetch found items:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchItems();
  }, []);
  // Random floating positions for background elements
  // const floatingItems = [
  //   { Icon: Watch, x: '10%', y: '20%', rot: 12, delay: 0 },
  //   { Icon: Umbrella, x: '85%', y: '15%', rot: -15, delay: 1 },
  //   { Icon: Wallet, x: '75%', y: '80%', rot: 8, delay: 0.5 },
  //   { Icon: Key, x: '15%', y: '75%', rot: -20, delay: 1.5 },
  // ];

  return (
    <div className="relative w-full h-screen overflow-hidden flex flex-col items-center justify-center p-6">

      {/* Background Decor */}
      <div className="absolute inset-0 pointer-events-none opacity-10">
        <svg className="w-full h-full" width="100%" height="100%">
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="currentColor" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
      </div>

      {/* Floating Elements */}
      {/* {floatingItems.map((item, index) => (
        <motion.div
          key={index}
          className="absolute text-[#2d2d2d] opacity-20 hover:opacity-100 hover:scale-110 transition-opacity cursor-pointer"
          style={{ left: item.x, top: item.y }}
          animate={{ 
            y: [0, -15, 0],
            rotate: [item.rot, item.rot - 5, item.rot]
          }}
          transition={{
            duration: 4 + index,
            repeat: Infinity,
            ease: "easeInOut",
            delay: item.delay
          }}
        >
          <item.Icon size={64} strokeWidth={1.5} />
        </motion.div>
      ))} */}

      {/* Main Content */}
      <div className="z-10 text-center max-w-4xl w-full">

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="mb-12"
        >
          <h1 className="font-display text-6xl md:text-8xl font-bold mb-4 leading-tight text-[#2d2d2d]">
            lost<span className="text-[#e07a5f]">N</span>found
          </h1>
          <div className="relative inline-block">
            <p className="font-hand text-2xl md:text-3xl text-[#5c5c5c] transform -rotate-2">
              "We find it before your mom finds out you lost it."
            </p>
            <div className="absolute -bottom-2 right-0 w-full h-1 bg-[#e07a5f] opacity-50 transform rotate-1"></div>
          </div>
        </motion.div>

        <div className="flex flex-col md:flex-row gap-8 justify-center items-center">

          {/* I Lost Something Card */}
          <motion.button
            whileHover={{ scale: 1.05, rotate: -2 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setAppState(AppState.LOST_FLOW)}
            className="group relative bg-[#f4f1ea] w-64 h-80 border-2 border-[#2d2d2d] paper-shadow p-6 flex flex-col items-center justify-between"
          >
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 w-4 h-12 bg-[#e07a5f]/20 transform -rotate-1 z-0"></div>
            <div className="w-16 h-4 bg-[#e07a5f]/20 absolute top-2 rotate-2"></div> {/* Tape look */}

            <div className="mt-8 bg-white border border-[#2d2d2d] p-4 rounded-full">
              <Search size={32} />
            </div>
            <div className="text-center">
              <h2 className="font-display text-2xl font-bold mb-2">I Lost Something</h2>
              <p className="font-hand text-lg text-gray-600">Help me remember.</p>
            </div>
            <div className="w-full h-1 border-t border-dashed border-[#2d2d2d] opacity-30"></div>
            <span className="font-bold text-sm uppercase tracking-widest text-[#e07a5f] group-hover:underline">Start Trace</span>
          </motion.button>

          {/* I Found Something Card */}
          <motion.button
            whileHover={{ scale: 1.05, rotate: 2 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setAppState(AppState.FOUND_FLOW)}
            className="group relative bg-[#2d2d2d] w-64 h-80 border-2 border-[#2d2d2d] paper-shadow p-6 flex flex-col items-center justify-between text-[#f4f1ea]"
          >
            <div className="w-16 h-4 bg-white/20 absolute top-2 -rotate-2"></div> {/* Tape look */}

            <div className="mt-8 bg-[#f4f1ea] text-[#2d2d2d] border border-[#f4f1ea] p-4 rounded-full">
              <MapPin size={32} />
            </div>
            <div className="text-center">
              <h2 className="font-display text-2xl font-bold mb-2">I Found Something</h2>
              <p className="font-hand text-lg text-gray-400">File an object.</p>
            </div>
            <div className="w-full h-1 border-t border-dashed border-gray-600 opacity-30"></div>
            <span className="font-bold text-sm uppercase tracking-widest text-[#81b29a] group-hover:underline">Submit Evidence</span>
          </motion.button>

        </div>

        {/* Found Items Gallery */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.8 }}
          className="mt-20 w-full max-w-6xl"
        >
          <div className="flex items-center justify-between mb-8 px-4">
            <h2 className="font-display text-3xl font-bold text-[#2d2d2d] flex items-center">
              <div className="w-2 h-8 bg-[#81b29a] mr-3"></div>
              Evidence Feed: Recently Found
            </h2>
            <div className="text-[#5c5c5c] font-hand text-xl rotate-1">
              "Someone might be looking for these..."
            </div>
          </div>

          {loading ? (
            <div className="flex justify-center items-center h-48">
              <Loader2 className="animate-spin text-[#e07a5f] mr-2" />
              <span className="font-display font-bold uppercase tracking-widest text-sm">Querying Archives...</span>
            </div>
          ) : foundItems.length === 0 ? (
            <div className="text-center py-12 border-2 border-dashed border-gray-300 rounded-lg">
              <p className="font-hand text-xl text-gray-400 italic">No evidence bagged yet today.</p>
            </div>
          ) : (
            <div className="relative">
              <div className="flex overflow-x-auto pb-8 pt-4 gap-6 no-scrollbar snap-x px-4">
                {foundItems.map((item, idx) => (
                  <motion.div
                    key={item.id}
                    whileHover={{ y: -10 }}
                    className="flex-shrink-0 w-72 bg-white border-2 border-[#2d2d2d] paper-shadow snap-start overflow-hidden relative group"
                  >
                    <div className="absolute top-2 right-2 z-10 bg-[#e07a5f] text-white px-2 py-1 text-[10px] font-bold uppercase tracking-tighter transform rotate-3">
                      Evidence #{item.id}
                    </div>
                    <div className="h-48 overflow-hidden bg-gray-100 border-b-2 border-[#2d2d2d] relative">
                      <img src={item.image_url.replace("http://localhost:8000", baseUrl)} alt={item.caption} className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" />
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors" />
                    </div>
                    <div className="p-4 bg-[#f4f1ea]">
                      <h3 className="font-display font-bold text-lg mb-1 truncate text-[#2d2d2d]">{item.caption}</h3>
                      <div className="flex items-center text-xs text-gray-500 mb-3 space-x-3">
                        <div className="flex items-center">
                          <MapPin size={12} className="mr-1 text-[#e07a5f]" />
                          {item.location}
                        </div>
                        <div className="flex items-center">
                          <Calendar size={12} className="mr-1 text-[#81b29a]" />
                          {new Date(item.date).toLocaleDateString()}
                        </div>
                      </div>
                      <Button
                        variant="secondary"
                        className="w-full py-2 text-xs"
                        size="sm"
                        onClick={() => setAppState(AppState.FOUND_FLOW)}
                      >
                        Inspect Item
                      </Button>
                    </div>
                    {/* Decorative "Tape" */}
                    <div className="absolute -top-1 left-4 w-12 h-4 bg-[#81b29a]/20 -rotate-2"></div>
                  </motion.div>
                ))}
              </div>
              {/* Shadow indicators for scroll */}
              <div className="absolute top-0 right-0 bottom-0 w-20 bg-gradient-to-l from-[#f4f1ea] to-transparent pointer-events-none z-10" />
              <div className="absolute top-0 left-0 bottom-0 w-20 bg-gradient-to-r from-[#f4f1ea] to-transparent pointer-events-none z-10" />
            </div>
          )}
        </motion.div>
      </div>

    </div>
  );
};