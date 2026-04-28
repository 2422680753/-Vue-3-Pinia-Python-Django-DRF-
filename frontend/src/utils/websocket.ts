import ReconnectingWebSocket from 'reconnecting-websocket'
import { ElMessage } from 'element-plus'

interface WebSocketOptions {
  onOpen?: () => void
  onClose?: () => void
  onMessage?: (data: any) => void
  onError?: (error: Event) => void
}

class WebSocketManager {
  private socket: ReconnectingWebSocket | null = null
  private url: string = ''
  private options: WebSocketOptions = {}
  private heartbeatInterval: number | null = null
  private isConnected: boolean = false

  connect(url: string, options: WebSocketOptions = {}): ReconnectingWebSocket {
    this.url = url
    this.options = options
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}${url}`
    
    this.socket = new ReconnectingWebSocket(wsUrl, [], {
      maxReconnectionDelay: 10000,
      minReconnectionDelay: 1000,
      reconnectionDelayGrowFactor: 1.3,
      connectionTimeout: 5000,
      maxRetries: 10,
      debug: false
    })

    this.socket.onopen = () => {
      this.isConnected = true
      this.startHeartbeat()
      this.options.onOpen?.()
    }

    this.socket.onclose = () => {
      this.isConnected = false
      this.stopHeartbeat()
      this.options.onClose?.()
    }

    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        this.options.onMessage?.(data)
      } catch (error) {
        console.error('WebSocket message parse error:', error)
      }
    }

    this.socket.onerror = (error) => {
      console.error('WebSocket error:', error)
      this.options.onError?.(error)
    }

    return this.socket
  }

  disconnect() {
    this.stopHeartbeat()
    if (this.socket) {
      this.socket.close()
      this.socket = null
    }
    this.isConnected = false
  }

  send(data: any) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data))
    } else {
      console.warn('WebSocket is not connected, message not sent:', data)
    }
  }

  private startHeartbeat() {
    this.heartbeatInterval = window.setInterval(() => {
      if (this.isConnected) {
        this.send({ type: 'heartbeat' })
      }
    }, 30000)
  }

  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }
  }

  getConnectionStatus(): boolean {
    return this.isConnected
  }
}

export const videoProgressSocket = new WebSocketManager()
export const examMonitoringSocket = new WebSocketManager()

export default WebSocketManager
