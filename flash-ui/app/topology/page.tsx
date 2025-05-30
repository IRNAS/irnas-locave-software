"use client"

import { useState, useEffect } from 'react'
import Link from 'next/link'

interface Neighbor extends Array<number> {
  0: number;  // nodeId
  1: number;  // interface
  2: number;  // rssi
}

interface TopologyNode {
  timestamp: number
  seconds_ago: number
  neighbors: Neighbor[]
  weather?: [number, number, number]
}

export default function Topology() {
  const [topology, setTopology] = useState<Record<string, TopologyNode>>({})

  useEffect(() => {
    const fetchTopology = async () => {
      const response = await fetch('/topology')
      const data = await response.json()
      setTopology(data)
    }

    fetchTopology()
    const topologyInterval = setInterval(fetchTopology, 2000)
    return () => clearInterval(topologyInterval)
  }, [])

  return (
    <main className="min-h-screen p-8 overflow-auto">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Network Topology</h1>
          <Link
            href="/"
            className="btn-primary"
          >
            Back to Dashboard
          </Link>
        </div>

        <div className="card p-6">
          {Object.entries(topology).length === 0 ? (
            <p>No topology data available</p>
          ) : (
            <div className="grid grid-cols-2 gap-6">
              {Object.entries(topology).map(([nodeId, data]) => (
                <div key={nodeId} className="card p-4">
                  <div className="text-xl font-medium mb-2">Node {nodeId}</div>
                  <div className="text-sm text-[var(--muted-foreground)] mb-4">Updated {data.seconds_ago}s ago</div>

                  {/* Display weather data if available */}
                  {data.weather ? (
                    <div className="text-sm text-[var(--muted-foreground)] mb-4">
                      <p>Weather Data:</p>
                      <p>Temperature: {data.weather[0]}°C</p>
                      <p>Humidity: {data.weather[1]}%</p>
                      <p>Air pressure: {data.weather[2] ? `${data.weather[2]} Pa` : "Not available"}</p>
                    </div>
                  ) : (
                    <div className="text-sm text-[var(--muted-foreground)] mb-4">No weather data available</div>
                  )}

                  <div className="space-y-2">
                    {data.neighbors.length === 0 ? (
                      <div className="text-sm text-[var(--muted-foreground)]">No neighbors detected</div>
                    ) : (
                      data.neighbors.map((neighbor, idx) => (
                        <div key={idx} className="flex items-center justify-between p-2 bg-[var(--muted)] rounded">
                          <span>Node {neighbor[0]}</span>
                          <span className="text-sm text-[var(--muted-foreground)]">
                            Interface {neighbor[1]} | RSSI: {neighbor[2]} dBm
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
