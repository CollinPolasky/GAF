const API_URL = "http://localhost:8000";

export const getAIMessage = async (userQuery, tools = null) => {
    try {
        const response = await fetch(`${API_URL}/chat`, {
            method: 'POST',
            credentials: 'include',
            headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
            },
            body: JSON.stringify({
            message: userQuery,
            tools: tools
            })
        });
        
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        
        return await response.json();
        } catch (error) {
        // Log the error
        console.error('Error:', error);
        if (error.message === 'Failed to fetch') {
            // If error is a failed network call
            return {
            role: "assistant",
            content: "Sorry, there was an error reaching the server."
            };
        }
        // If error is a server error
        return {
            role: "assistant",
            content: "Sorry, there was an error processing your request."
        };
    }
};

export const resetChat = async () => {
  try {
    const response = await fetch(`${API_URL}/reset`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error('Network response was not ok');
    }

    return await response.json();
  } catch (error) {
    console.error('Error:', error);
    return {
      role: "assistant",
      content: "Sorry, there was an error resetting the chat."
    };
  }
};
