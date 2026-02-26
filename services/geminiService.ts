export const generateDetectiveResponse = async (
  history: { role: string; content: string }[],
  userInput: string
): Promise<{ text: string; tags: string[]; confidenceDelta: number; recoveryProbability?: number }> => {

  const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
  try {
    const response = await fetch(`${baseUrl}/api/detective`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        history,
        userInput
      })
    });

    if (!response.ok) {
      throw new Error("Backend error");
    }

    const parsed = await response.json();

    return {
      text: parsed.text || "Could you describe it further?",
      tags: parsed.tags || [],
      confidenceDelta: parsed.confidenceDelta || 2,
      recoveryProbability: parsed.recoveryProbability
    };

  } catch (error) {
    console.error("Detective API Error:", error);

    return {
      text: "I'm having trouble connecting to the archives. Can you tell me that again?",
      tags: [],
      confidenceDelta: 0
    };
  }
};
