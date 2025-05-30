"use client"

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'

interface NodeData {
  last_seen: number
  seconds_ago: number
  ttl: number
}

// TODO: add periodic updates to nodes and mac addresses of expanded node
export default function BLEResults() {
  const [nodes, setNodes] = useState<Record<string, NodeData>>({})
  const [loadingNodes, setLoadingNodes] = useState<boolean>(true)
  const [errorNodes, setErrorNodes] = useState<string | null>(null)

  // Fetch nodes on component mount
  useEffect(() => {
    const fetchNodes = async () => {
      try {
        const response = await fetch('/nodes') // Removed '/api' prefix
        if (!response.ok) throw new Error('Failed to fetch nodes')
        const data: Record<string, NodeData> = await response.json()
        setNodes(data)
        setLoadingNodes(false)
      } catch (error: unknown) {
        if (error instanceof Error) {
          setErrorNodes(error.message)
        } else {
          setErrorNodes('An unexpected error occurred')
        }
        setLoadingNodes(false)
      }
    }

    fetchNodes()
  }, [])

  return (
    <main className="min-h-screen p-8 overflow-auto">
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">BLE Results</h1>
          <Link
            href="/"
            className="btn-primary"
          >
            Back to Dashboard
          </Link>
        </div>

        {loadingNodes && <p>Loading nodes...</p>}
        {errorNodes && <p className="text-red-500">{errorNodes}</p>}
        {!loadingNodes && !errorNodes && (
          <ul className="space-y-4">
            {Object.entries(nodes).map(([nodeId, data]) => (
              <NodeItem key={nodeId} nodeId={nodeId} data={data} />
            ))}
          </ul>
        )}
      </div>
    </main>
  )
}

interface NodeItemProps {
  nodeId: string
  data: NodeData
}

interface DeviceData {
  id: number,
  timestamp: number
}

function NodeItem({ nodeId }: NodeItemProps) {
  const [isExpanded, setIsExpanded] = useState<boolean>(false)
  const [macAddresses, setMacAddresses] = useState<DeviceData[]>([])



  const fetchMacAddresses = useCallback(async () => {
    try {
      const response = await fetch(`/ble_results/${nodeId}`) // Removed '/api' prefix
      if (!response.ok) throw new Error('Failed to fetch MAC addresses')
      const data: DeviceData[] = await response.json()
      setMacAddresses(data)
    } catch (error: unknown) {
      if (error instanceof Error) {
        console.error(error.message)
      }
    }
  }, [nodeId])

  useEffect(() => {
    const interval = setInterval(() => {
      fetchMacAddresses();
    }, 3000);

    return () => clearInterval(interval);
  }, [fetchMacAddresses]);

  const toggleExpand = () => {
    if (!isExpanded) {
      fetchMacAddresses()
    }
    setIsExpanded(!isExpanded)
  }


  return (
    <li className="card p-4">
      <div
        onClick={toggleExpand}
        className="flex justify-between items-center cursor-pointer"
      >
        <span className="font-medium">Node {nodeId}</span>
        <span className="text-[var(--muted-foreground)]">{isExpanded ? '▲' : '▼'}</span>
      </div>
      {isExpanded && (
        <div className="mt-4 flex justify-center">
          <table className="min-w-full border-collapse border border-[var(--border)]">
            <thead>
              <tr>
                <th className="border border-[var(--border)] px-4 py-2">Device ID</th>
                <th className="border border-[var(--border)] px-4 py-2">Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {macAddresses.length === 0 ? (
                <tr>
                  <td colSpan={2} className="border border-[var(--border)] px-4 py-2 text-center text-[var(--muted-foreground)]">
                    No EarTags detected
                  </td>
                </tr>
              ) : (
                macAddresses.map((mac) => (
                  <tr key={mac.id}>
                    <td className="border border-[var(--border)] px-4 py-2">{mac.id}</td>
                    <td className="border border-[var(--border)] px-4 py-2">{mac.timestamp}s ago</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </li>
  )
}
