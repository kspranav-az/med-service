import { useState } from "react"
import { ChatTab } from "./components/ChatTab"
import { AutocompleteTab } from "./components/AutocompleteTab"
import { HealthTab } from "./components/HealthTab"

type Tab = "chat" | "autocomplete" | "health"

const tabs: { id: Tab; label: string }[] = [
  { id: "chat", label: "Chat" },
  { id: "autocomplete", label: "Autocomplete" },
  { id: "health", label: "Health" },
]

function App() {
  const [activeTab, setActiveTab] = useState<Tab>("chat")

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 dark:bg-gray-950 dark:text-gray-100">
      <header className="border-b border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-purple-700 dark:text-purple-400">
              MedService Dev Console
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Test the RAG Chat Agent and Semantic Autocomplete services.
            </p>
          </div>
          <nav className="flex gap-2">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? "bg-purple-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        {activeTab === "chat" && <ChatTab />}
        {activeTab === "autocomplete" && <AutocompleteTab />}
        {activeTab === "health" && <HealthTab />}
      </main>
    </div>
  )
}

export default App
