# Kontextrument

Kontextrument is a desktop/CLI assistant designed to streamline developing software with Large Language Models (LLMs). It's a personal project built to prepare a codebase for large context windows, interact with web-based LLMs, and apply generated changes back to the source files—all from a single, unified interface.

The tool was almost entirely created using itself (except the first version, obviously), following both "bootstrap" and "dog food" principles.

---

## The main idea is simple

* **Bring Your Own Chatbot** - Use any web chat service you want: ChatGPT, Gemini, Claude, Deepseek, Perplexity AI, or your local models (if you happen to own a data center). You can switch between chatbots for different tasks without any problems (I did).
* **Control your context** - You explicitly decide which files to add to the prompt and which to exclude. You can set up different presets for different tasks, including only the code related to that task.
* **Automate the integration** - Manually integrating AI replies into code took a lot of time and effort. The idea was to take an LLM's reply and automatically apply it as changes to existing code, often across multiple files. Some people request replies in JSON, but I've personally gotten more consistent results with Markdown—and Markdown replies are much easier to read.
* **Preview then integrate** - You can preview the changes before integrating them. There's no rollback support, and I don't plan on implementing it, because Git already solves this problem perfectly.
* **Commit the changes to VCS** - This is my main advice. Use Git or any other version control system, even if you don't plan to share the code. On multiple occasions, I've had to restart a feature development, and doing so without version control would have been a headache.

---

## Features

Kontextrument combines several tools into a modular, tab-based GUI backed by powerful command-line functionality.

* **Context Management:**
    * **Generation:** Create structured Markdown files from your project. Configure exactly what to include or exclude using `.context` files, with built-in support for `.gitignore` rules. The GUI provides a live preview as you adjust settings.
    * **Application:** Apply LLM-generated Markdown patches directly to your files. The tool parses and performs commands for file creation, deletion, and in-place replacements. A dry-run mode and diff viewer let you review all changes before applying them.

* **Unified GUI:** A central hub for your entire LLM workflow, featuring:
    * **Browser Tab:** An integrated web browser for direct interaction with your favorite web-based LLMs like Gemini, ChatGPT, and Claude. Includes bookmark management for quick access.
    * **Workspace Tab:** A small workspace with essential tools, including:
        * A file explorer for project navigation. With ability to view images and play sounds for convenience.
        * A simple code editor with syntax highlighting.
        * A command launcher to run terminal commands (usually compilation or tests) and easily copy output to the clipboard.
    * **Git Tab:** A simple **Git GUI** to manage changes without leaving the application. View staged/unstaged changes, inspect diffs, and perform common operations like commit, push, or pull.
    * **Module Management:** A settings panel to enable or disable any of the main feature tabs.

* **Command-Line Tools:**
    * In addition to the GUI, Kontextrument provides robust CLI entry points (`ktr create`, `ktr apply`) for context generation and application, perfect for platforms where a GUI is unavailable, like a Termux or SSH session.

* **Standalone Build:**
    * The standalone **build** is made with `PyInstaller`, with all its pros and cons. On one hand, it allows you to download a ready to use executable and use it without worrying about dependencies. On the other hand, antivirus software, especially Windows Defender, seems to hate `PyInstaller`.
    * Binary for linux contains WebKit, so it's 5 times bigger than binary for Windows (that uses Edge, provided by the OS).

---

## Practical reactive development philosophy and the absence of roadmap.

You may probably recognise, that there is no bigger plan or scheme behind the tool.
The core philosophy behind this tool's feature list can be summarized in one phrase:
**"If i needed it more than twice, I'm making a feature for it."**

If you're using the tool and missing a feature more than twice - [let me know](https://github.com/VP-Project/kontextrument/issues).

---

## Requirements

### CLI mode:
- **python** 3.13 (but should work with any modern python3 version)
- **pathspec** 0.12.1
### GUI mode :
- *everything that CLI mode needs*
- **wxpython** 4.2.3
- **pypubsub** 4.0.3
-  **pywinpty** on Windows or **ptyprocess** on other operating systems.

---

## Who is it for?

- Myself. The tool was initially created by myself for myself, and I didn't plan on sharing it.
- People who don't want to or can't pay for multiple subscriptions.
- Anyone who cares to try and finds my workflow suitable.

---

## Usual workflow

- Launch the tool and pick the folder with your project.
- When developing a new feature - add a new section for it.
- Add relevant files to the context and remove irrelevant (from personal experience, it's better to keep the estimated tokens count below 80K, it helps current generation LLMs to consistently follow the formatting instructions).
- (optional) Put a brief one paragraph description of your project to "Preamble" field.
- Write the task description for LLM in the "Appendix" field.
- Enable Formatting rules and Appendix checkboxes.
- Copy the generated prompt to clipboard.
- Open your favorite chatbot in the browser tab.
- Paste the prompt into a new chat and wait for the reply.
- Copy the reply in markdown form (there is usually a button for this) and paste it into the field on "Apply Context" tab.
- Press "Dry run", check the results, then press "Parse and create" to actually integrate the changes.
- Test your changes (you can use workspace tab for it or your favorite IDE outside the app) to find bugs and problems.
- Report bugs and problems to you chatbot (mostly, using the same chat is okay). Copy reply and apply it again. Repeat until you're satisfied with the result. If you hit a dead end, try starting a new chat with updated listing and task description (resolving a problem instead of feature implementation).
- Commit the changes into version control system (even if just locally).
- Now you are ready to start working on another task.

---

## Why not just use an AI-powered IDE like everyone else does?

Many people use AI-powered IDEs, and they are very promising tools. But I have a few reasons for continuing to use and improve this tool:

1.  Most LLM-powered IDEs require an API, which usually means paying per token. While chatbots have rate limits, they often provide tokens more affordably for active users. Modern IDEs also have subscriptions, but they limit which models you can use. You still can't use your existing ChatGPT, Claude, or Gemini subscription with an IDE.
2.  This tool gives me explicit control over what project information goes into the LLM's context window.
3.  I've tried a couple of AI-powered IDEs and found that in most cases, I can achieve a similar result with the same or less effort using this tool. The real downside of Kontextrument is that it can't act like an agent, whereas some AI-powered IDEs can. But to be honest, I've never been able to get good results from an agent once the codebase becomes large enough.
4.  Gemini Gems and custom GPTs can provide great results when used with documentation for your libraries (including ones that aren't popular enough for training data or aren't available publicly). These custom AIs usually can't be used from IDEs.

I'm not trying to state that IDEs are somehow inferior or discourage anyone from using them, just sharing the alternative with those who, like me, might need it.

I've honestly thought about rewriting the whole tool as a VS Code extension, but rewriting it in JS (even with LLMs) isn't what I want to do right now. I'm currently fine with using it as a separate tool alongside a full-featured IDE. Maybe someday I'll consider it, but it's a huge undertaking—so not today and not tomorrow.
