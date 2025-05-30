"use client"

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'

interface Message {
  timestamp: number
  seconds_ago: number
  source: number
  dest: number
  type: 'sent' | 'received'
  content: string
}

export default function Home() {
  const [nodes, setNodes] = useState<Record<string, {
    last_seen: number,
    seconds_ago: number,
    ttl: number
  }>>({})
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [botStatus, setBotStatus] = useState<'online' | 'offline'>('offline')
  const messagesContainerRef = useRef<HTMLDivElement>(null)

  const atBottomRef = useRef(true)

  const isAtBottom = () => {
    const container = messagesContainerRef.current
    if (!container) return

    const threshold = 10
    const isAtBottom =
      Math.abs(container.scrollHeight - container.scrollTop - container.clientHeight) <= threshold

    atBottomRef.current = isAtBottom
  };

  useEffect(() => {
    const container = messagesContainerRef.current
    if (!container || !atBottomRef.current) return

    container.scrollTo({
      top: container.scrollHeight,
      behavior: 'smooth'
    })
  }, [messages])

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8080')

    return () => ws.close()
  }, [])

  useEffect(() => {
    const fetchNodes = async () => {
      const response = await fetch('/nodes')
      const data = await response.json()
      setNodes(data)
    }

    fetchNodes()

    const interval = setInterval(fetchNodes, 2000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const fetchMessages = async () => {
      const response = await fetch('/messages')
      const data = await response.json()
      isAtBottom();
      setMessages(data)
    }

    fetchMessages()
    const messageInterval = setInterval(fetchMessages, 2000)
    return () => {
      clearInterval(messageInterval)
    }
  }, [])

  useEffect(() => {
    const fetchBotStatus = async () => {
      try {
        const response = await fetch('/bot/status')
        const data = await response.json()
        setBotStatus(data.status)
      } catch (error) {
        console.error('Failed to fetch bot status:', error)
      }
    }

    fetchBotStatus()
    const statusInterval = setInterval(fetchBotStatus, 5000)
    return () => clearInterval(statusInterval)
  }, [])

  const broadcastMessage = (msg: string) => {
    fetch('/broadcast', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg })
    })
    setMessage('')
  }

  const getTimestampedMessage = (baseMsg: string) => {
    return `${baseMsg} (${new Date().toLocaleTimeString()})`
  }

  return (
    <main className="min-h-screen p-8 overflow-auto">
      <div className="max-w-md mx-auto space-y-6 mb-8">
        <div className="flex justify-between items-center mb-6">
          <div className="w-full">
            <div className="flex justify-between items-center">
              <h1 className="text-2xl font-bold">Dashboard</h1>
              <div className="flex items-center gap-2">
                <span className="text-sm text-[var(--muted-foreground)]">Bot Status:</span>
                <span className={`px-2 py-1 rounded text-sm ${
                  botStatus === 'online'
                    ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100'
                    : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100'
                }`}>
                  {botStatus}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-2 w-full">
              <Link
                href="/topology"
                className="btn-primary flex-1 text-center"
              >
                View Topology
              </Link>
              <Link
                href="/ble_results"
                className="btn-secondary flex-1 text-center"
              >
                BLE Results
              </Link>
              <Link
                href="/bot"
                className="btn-secondary flex-1 text-center"
              >
                Bot Control
              </Link>
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex gap-2">
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  broadcastMessage(message)
                }
              }}
              placeholder="Enter message to broadcast"
              className="flex-1 p-2 border rounded bg-[var(--card)] text-[var(--card-foreground)] border-[var(--border)]"
            />
            <button
              onClick={() => broadcastMessage(message)}
              className="btn-secondary"
            >
              Send
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => broadcastMessage(getTimestampedMessage('Hi from base'))}
              className="btn-secondary"
            >
              Hi from base
            </button>
            <button
              onClick={() => broadcastMessage(getTimestampedMessage('Ping test'))}
              className="btn-secondary"
            >
              Ping test
            </button>
          </div>
        </div>

        <div className="card p-4 h-[500px] flex flex-col">
          <h2 className="text-lg font-semibold mb-3">Messages</h2>
          <div ref={messagesContainerRef} className="flex-1 overflow-y-auto space-y-4">
            {messages.map((msg, index) => (
              <div key={index} className={`flex ${msg.type === 'sent' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[70%] ${msg.type === 'sent'
                  ? 'bg-[var(--primary)] text-white rounded-l-lg rounded-tr-lg'
                  : 'bg-[var(--muted)] text-[var(--card-foreground)] rounded-r-lg rounded-tl-lg'
                  } p-3`}
                >
                  <div className="text-xs mb-1 opacity-75">
                    {msg.type === 'received' ? `From Node ${msg.source} • ` : ''}
                    {msg.seconds_ago}s ago
                  </div>
                  <div>{msg.content}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card p-4">
          <h2 className="text-lg font-semibold mb-3">Node Status</h2>
          <div className="space-y-2">
            {Object.entries(nodes).length === 0 ? (
              <p>No nodes detected yet</p>
            ) : (
              Object.entries(nodes).map(([nodeId, data]) => (
                <div key={nodeId} className="flex justify-between items-center border-b border-[var(--border)] py-2">
                  <span className="font-medium">Node {nodeId}</span>
                  <span className="text-sm text-[var(--muted-foreground)]">
                    {data.seconds_ago} seconds ago
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </main>
  )
}
