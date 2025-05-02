import React, { useState, useEffect } from 'react';
import './ContractorList.css';

function ContractorList() {
  const [contractors, setContractors] = useState([]);
  const [insights, setInsights] = useState({});
  const [contractorScores, setContractorScores] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedInsights, setExpandedInsights] = useState({});

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch contractor details
        const detailsResponse = await fetch('/data/contractor_details.json');
        if (!detailsResponse.ok) {
          throw new Error(`HTTP error! Status: ${detailsResponse.status}`);
        }
        const detailsData = await detailsResponse.json();
        
        // Try to fetch insights
        let insightsMap = {};
        let scoresMap = {};
        try {
          const insightsResponse = await fetch('/data/contractor_insights.json');
          if (insightsResponse.ok) {
            const insightsData = await insightsResponse.json();
            // Convert insights array to maps for easy lookup
            insightsMap = insightsData.reduce((map, item) => {
              map[item.id] = item.insight;
              return map;
            }, {});
            
            scoresMap = insightsData.reduce((map, item) => {
              map[item.id] = item.score;
              return map;
            }, {});
          }
        } catch (insightError) {
          console.log("No insights available:", insightError);
        }
        
        setContractors(detailsData);
        setInsights(insightsMap);
        setContractorScores(scoresMap);
        setLoading(false);
      } catch (error) {
        console.error("Error fetching data:", error);
        setError("Failed to load contractor data. Please try again later.");
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const toggleInsight = (contractorId) => {
    setExpandedInsights(prev => ({
      ...prev,
      [contractorId]: !prev[contractorId]
    }));
  };

  if (loading) {
    return <div className="loading">Loading contractors...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  // Sort contractors by score in descending order
  const sortedContractors = [...contractors].sort((a, b) => {
    const scoreA = contractorScores[a.id] || 0;
    const scoreB = contractorScores[b.id] || 0;
    return scoreB - scoreA; // Descending order
  });

  return (
    <div className="contractor-list">
      <h1>Roofing Contractors</h1>
      <div className="contractor-grid">
        {sortedContractors.map((contractor) => (
          <div key={contractor.id} className="contractor-card">
            <div className="contractor-card-header">
              <h2 className="contractor-name">{contractor.name}</h2>
              
              {contractorScores[contractor.id] && (
                <div className="contractor-score">
                  <span>Lead Quality Score: {contractorScores[contractor.id]}</span>
                </div>
              )}
              
              {contractor.website && (
                <div className="contractor-website">
                  <a href={contractor.website} target="_blank" rel="noopener noreferrer">
                    Visit Website
                  </a>
                </div>
              )}
            </div>
            
            <div className="contractor-card-content">
              <div className={`contractor-about ${!contractor.about || contractor.about.length === 0 ? 'minimal-about' : ''}`}>
                <h3>About</h3>
                {contractor.about && contractor.about.length > 0 ? (
                  <p>
                    {contractor.about.length > 400
                      ? `${contractor.about.substring(0, 400)}...`
                      : contractor.about}
                  </p>
                ) : (
                  <p className="no-description">No About Description Available</p>
                )}
              </div>
            </div>
            
            {insights[contractor.id] && (
              <div className={`contractor-insight ${expandedInsights[contractor.id] ? 'expanded-insight' : ''}`}>
                <h3>Lead Quality Insight</h3>
                <div className="insight-content">
                  <p>
                    {expandedInsights[contractor.id] || insights[contractor.id].length <= 500
                      ? insights[contractor.id]
                      : `${insights[contractor.id].substring(0, 500)}...`}
                  </p>
                  {insights[contractor.id].length > 500 && (
                    <button 
                      className="read-more-btn" 
                      onClick={() => toggleInsight(contractor.id)}
                    >
                      {expandedInsights[contractor.id] ? 'Show Less' : 'Read More'}
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default ContractorList; 