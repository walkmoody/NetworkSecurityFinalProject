import type { ClassInfo } from '../components/ClassCard'

// Mock data until the backend provides the user's classes.
export const classes: ClassInfo[] = [
  {
    id: 'CS5342',
    code: 'CS 5342',
    name: 'Network Security',
    description:
      'Firewalls, cryptography, authentication, intrusion detection, and securing network protocols.',
    topics: ['Firewalls', 'Cryptography', 'TLS', 'IDS/IPS', 'VPNs'],
  },
]

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

// Mock quiz until the backend's Quiz agent is wired up.
export const quizGenerateSteps = ['Retrieving course materials', 'Generating questions', 'Validating questions and citations']
export const quizGradeSteps = ['Checking answers', 'Grading open-ended responses', 'Writing feedback']

export type QuizQuestion = { id: string; prompt: string; explanation: string; citation: Citation } & (
  | { type: 'multiple_choice'; options: string[]; answer: number }
  | { type: 'true_false'; answer: boolean }
  | { type: 'open_ended'; keywords: string[] }
)

export const mockQuiz: QuizQuestion[] = [
  {
    id: 'q1',
    type: 'multiple_choice',
    prompt: 'Which type of firewall tracks the state of network connections?',
    options: ['Packet-filtering firewall', 'Stateful inspection firewall', 'Proxy server', 'Network hub'],
    answer: 1,
    explanation: 'Stateful firewalls keep a table of active connections and use it when deciding whether to allow packets.',
    citation: { source: 'Lecture 6: Firewalls', section: 'Stateful inspection' },
  },
  {
    id: 'q2',
    type: 'multiple_choice',
    prompt: 'Which key exchange gives TLS 1.3 forward secrecy?',
    options: ['Static RSA', 'Ephemeral (EC)DHE', 'Pre-shared MD5 keys', 'Diffie-Hellman with fixed keys'],
    answer: 1,
    explanation: 'TLS 1.3 removed static RSA key exchange; ephemeral (EC)DHE keys are thrown away after the session.',
    citation: { source: 'RFC 8446', section: '1.2 Major Differences from TLS 1.2' },
  },
  {
    id: 'q3',
    type: 'multiple_choice',
    prompt: 'What does an IDS do that a typical firewall does not?',
    options: ['Assign IP addresses', 'Detect suspicious activity by inspecting traffic patterns', 'Route packets between networks', 'Encrypt traffic'],
    answer: 1,
    explanation: 'An intrusion detection system analyzes traffic for signatures or anomalies and raises alerts.',
    citation: { source: 'Lecture 7: Intrusion Detection', section: 'Signature vs. anomaly detection' },
  },
  {
    id: 'q4',
    type: 'true_false',
    prompt: 'Symmetric encryption uses the same key to encrypt and decrypt.',
    answer: true,
    explanation: 'Symmetric ciphers like AES share one secret key between both parties.',
    citation: { source: 'Lecture 4: Cryptography', section: 'Symmetric-key ciphers' },
  },
  {
    id: 'q5',
    type: 'true_false',
    prompt: 'A VPN hides your traffic from the VPN provider itself.',
    answer: false,
    explanation: 'The VPN provider terminates the tunnel, so it can see your traffic unless it is also encrypted end-to-end.',
    citation: { source: 'Lecture 10: VPNs', section: 'Trust model' },
  },
  {
    id: 'q6',
    type: 'open_ended',
    prompt: 'Explain how a man-in-the-middle attack works and one way to defend against it.',
    keywords: ['intercept', 'relay', 'tls', 'certificate', 'encrypt', 'authentication'],
    explanation: 'A strong answer describes an attacker intercepting/relaying traffic and names a defense such as TLS with certificate validation.',
    citation: { source: 'Lecture 3: Network Attacks', section: 'Man-in-the-middle' },
  },
]
