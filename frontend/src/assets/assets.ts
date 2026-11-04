export type Citation = { source: string; section: string }

// Mock Tutor answers, picked by keyword until the backend's Tutor agent is wired up.
export const tutorSteps = ['Reading the question', 'Searching course materials', 'Checking citations', 'Drafting an answer']

export const tutorSuggestions = [
  'What is the difference between a stateful and stateless firewall?',
  'How does the TLS handshake work?',
  'What is a man-in-the-middle attack?',
]

export const tutorAnswers: { keywords: string[]; text: string; citations: Citation[] }[] = [
  {
    keywords: ['firewall', 'stateful', 'stateless'],
    text: 'A stateless firewall filters each packet on its own using rules about source/destination IP, port, and protocol. A stateful firewall also tracks the state of connections, so it can allow return traffic for connections that were opened from inside the network and drop packets that do not belong to a known session. Stateful inspection is more secure but uses more memory and CPU.',
    citations: [
      { source: 'Lecture 6: Firewalls', section: 'Packet filtering vs. stateful inspection' },
      { source: 'Kurose & Ross, Ch. 8', section: '8.9.1 Firewalls' },
    ],
  },
  {
    keywords: ['tls', 'ssl', 'handshake', 'https'],
    text: 'In a TLS 1.3 handshake the client sends a ClientHello with supported cipher suites and a key share. The server replies with a ServerHello, its own key share, and its certificate. Both sides derive the same session keys using (EC)DHE, the client verifies the certificate chain, and Finished messages confirm that nothing was tampered with. After that, application data is encrypted with the shared symmetric keys.',
    citations: [
      { source: 'Lecture 9: TLS', section: 'TLS 1.3 handshake' },
      { source: 'RFC 8446', section: '2. Protocol Overview' },
    ],
  },
  {
    keywords: ['mitm', 'man-in-the-middle', 'man in the middle'],
    text: 'In a man-in-the-middle attack, an attacker secretly relays (and possibly changes) traffic between two parties who think they are talking directly. Common techniques include ARP spoofing and rogue Wi-Fi access points. Defenses include authenticated encryption such as TLS with certificate validation, HSTS, and mutual authentication.',
    citations: [{ source: 'Lecture 3: Network Attacks', section: 'Man-in-the-middle' }],
  },
]

export const tutorFallback = {
  text: 'This is a mock answer. Once the backend is connected, the Tutor agent will answer using the course knowledge base and cite the materials it used.',
  citations: [{ source: 'CS 5342 course materials', section: 'Mock citation' }],
}

// Public quiz shape returned by the backend. Answer keys never leave the server.
export type QuizQuestion = {
  question_id: string
  type: 'multiple_choice' | 'true_false' | 'open_ended'
  text: string
  options: Record<string, string>
  max_points: number
}

export type Quiz = {
  quiz_id: string
  attempt_id: string
  course_id: string
  status: string
  questions: QuizQuestion[]
}

export type QuizCitation = {
  chunk_id: string
  document_id: string
  title: string
  page: number
  source_type: string
  source_url: string | null
}

export type QuizResult = {
  attempt_id: string
  status: 'graded'
  points_awarded: number
  max_points: number
  results: {
    question_id: string
    points_awarded: number
    max_points: number
    feedback: string
    citations: QuizCitation[]
  }[]
}
