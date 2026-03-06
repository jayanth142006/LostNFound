export const generateDetectiveResponse = async (
  history: { role: string; content: string }[],
  userInput: string,
  currentDetails: {
    category: string;
    color: string;
    location: string;
    time: string;
    days_since_loss: number;
  }
): Promise<{
  text: string;
  tags: string[];
  recovery_probability: number;
  current_category?: string;
  current_color?: string;
  current_location?: string;
  current_time?: string;
  current_days?: number;
}> => {

  const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
  try {
    const response = await fetch(`${baseUrl}/api/detective`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        history,
        userInput,
        ...currentDetails
      })
    });

    if (!response.ok) {
      throw new Error("Backend error");
    }

    const parsed = await response.json();

    return {
      text: parsed.text || "Could you describe it further?",
      tags: parsed.tags || [],
      recovery_probability: parsed.recovery_probability || 10,
      current_category: parsed.current_category,
      current_color: parsed.current_color,
      current_location: parsed.current_location,
      current_time: parsed.current_time,
      current_days: parsed.current_days
    };

  } catch (error) {
    console.error("Detective API Error:", error);

    return {
      text: "I'm having trouble connecting to the archives. Can you tell me that again?",
      tags: [],
      recovery_probability: 10
    };
  }
};
