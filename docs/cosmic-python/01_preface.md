sect1
## Preface
You may be wondering who we are and why we wrote this book.
At the end of Harry's last book, [*Test-Driven Development with Python*](http//www.obeythetestinggoat.com) (O'Reilly), he found himself asking a bunch of questions about architecture, such as, What's the best way of structuring your application so that it's easy to test? More specifically, so that your core business logic is covered by unit tests, and so that you minimize the number of integration and end-to-end tests you need? He made vague references to \"Hexagonal Architecture\" and \"Ports and Adapters\" and \"Functional Core, Imperative Shell,\" but if he was honest, he'd have to admit that these weren't things he really understood or had done in practice.
And then he was lucky enough to run into Bob, who has the answers to all these questions.
Bob ended up as a software architect because nobody else on his team was doing it. He turned out to be pretty bad at it, but *he* was lucky enough to run into Ian Cooper, who taught him new ways of writing and thinking about code.
sect2
### Managing Complexity, Solving Business Problems
We both work for MADE.com, a European ecommerce company that sells furniture online; there, we apply the techniques in this book to build distributed systems that model real-world business problems. Our example domain is the first system Bob built for MADE, and this book is an attempt to write down all the *stuff* we have to teach new programmers when they join one of our teams.
MADE.com operates a global supply chain of freight partners and manufacturers. To keep costs low, we try to optimize the delivery of stock to our warehouses so that we don't have unsold goods lying around the place.
Ideally, the sofa that you want to buy will arrive in port on the very day that you decide to buy it, and we'll ship it straight to your house without ever storing it. Getting the timing right is a tricky balancing act when goods take three months to arrive by container ship. Along the way, things get broken or water damaged, storms cause unexpected delays, logistics partners mishandle goods, paperwork goes missing, customers change their minds and amend their orders, and so on.
We solve those problems by building intelligent software representing the kinds of operations taking place in the real world so that we can automate as much of the business as possible.
sect2
### Why Python?
If you're reading this book, we probably don't need to convince you that Python is great, so the real question is \"Why does the *Python* community need a book like this?\" The answer is about Python's popularity and maturity although Python is probably the world's fastest-growing programming language and is nearing the top of the absolute popularity tables, it's only just starting to take on the kinds of problems that the C# and Java world has been working on for years. Startups become real businesses; web apps and scripted automations are becoming (whisper it) *enterprise* *software*.
In the Python world, we often quote the Zen of Python \"There should be one---​and preferably only one---​obvious way to do it.\"^\[[1](#_footnotedef_1 "View footnote.")\]^ Unfortunately, as project size grows, the most obvious way of doing things isn't always the way that helps you manage complexity and evolving requirements.
None of the techniques and patterns we discuss in this book are new, but they are mostly new to the Python world. And this book isn't a replacement for the classics in the field such as Eric Evans's *Domain-Driven Design* or Martin Fowler's *Patterns of Enterprise Application Architecture* (both published by Addison-Wesley Professional)---which we often refer to and encourage you to go and read.
But all the classic code examples in the literature do tend to be written in Java or C++/#, and if you're a Python person and haven't used either of those languages in a long time (or indeed ever), those code listings can be quite...​trying. There's a reason the latest edition of that other classic text, Fowler's *Refactoring* (Addison-Wesley Professional), is in JavaScript.
### TDD, DDD, and Event-Driven Architecture
In order of notoriety, we know of three tools for managing complexity
1.  *Test-driven development* (TDD) helps us to build code that is correct and enables us to refactor or add new features, without fear of regression. But it can be hard to get the best out of our tests How do we make sure that they run as fast as possible? That we get as much coverage and feedback from fast, dependency-free unit tests and have the minimum number of slower, flaky end-to-end tests?
2.  *Domain-driven design* (DDD) asks us to focus our efforts on building a good model of the business domain, but how do we make sure that our models aren't encumbered with infrastructure concerns and don't become hard to change?
3.  Loosely coupled (micro)services integrated via messages (sometimes called *reactive microservices*) are a well-established answer to managing complexity across multiple applications or business domains. But it's not always obvious how to make them fit with the established tools of the Python world---​Flask, Django, Celery, and so on.
+-----------------------------------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|  title                         | Don't be put off if you're not working with (or interested in) microservices. The vast majority of the patterns we discuss, including much of the event-driven architecture material, is absolutely applicable in a monolithic architecture. |
| Note                              |                                                                                                                                                                                                                                              |
|                                |                                                                                                                                                                                                                                              |
+-----------------------------------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
Our aim with this book is to introduce several classic architectural patterns and show how they support TDD, DDD, and event-driven services. We hope it will serve as a reference for implementing them in a Pythonic way, and that people can use it as a first step toward further research in this field.
sect2
### Who Should Read This Book
Here are a few things we assume about you, dear reader
ulist
- You've been close to some reasonably complex Python applications.
- You've seen some of the pain that comes with trying to manage that complexity.
- You don't necessarily know anything about DDD or any of the classic application architecture patterns.
We structure our explorations of architectural patterns around an example app, building it up chapter by chapter. We use TDD at work, so we tend to show listings of tests first, followed by implementation. If you're not used to working test-first, it may feel a little strange at the beginning, but we hope you'll soon get used to seeing code \"being used\" (i.e., from the outside) before you see how it's built on the inside.
We use some specific Python frameworks and technologies, including Flask, SQLAlchemy, and pytest, as well as Docker and Redis. If you're already familiar with them, that won't hurt, but we don't think it's required. One of our main aims with this book is to build an architecture for which specific technology choices become minor implementation details.
sect2
### A Brief Overview of What You'll Learn
The book is divided into two parts; here's a look at the topics we'll cover and the chapters they live in.
sect3
#### [#part1](#part1){data-type="xref" xrefstyle="chap-num-title"}
dlist
Domain modeling and DDD (Chapters [1](#chapter_01_domain_model), [2](#chapter_02_repository) and [7](#chapter_07_aggregate))
At some level, everyone has learned the lesson that complex business problems need to be reflected in code, in the form of a model of the domain. But why does it always seem to be so hard to do without getting tangled up with infrastructure concerns, our web frameworks, or whatever else? In the first chapter we give a broad overview of *domain modeling* and DDD, and we show how to get started with a model that has no external dependencies, and fast unit tests. Later we return to DDD patterns to discuss how to choose the right aggregate, and how this choice relates to questions of data integrity.
Repository, Service Layer, and Unit of Work patterns (Chapters [2](#chapter_02_repository), [4](#chapter_04_service_layer), and [5](#chapter_05_high_gear_low_gear))
In these three chapters we present three closely related and mutually reinforcing patterns that support our ambition to keep the model free of extraneous dependencies. We build a layer of abstraction around persistent storage, and we build a service layer to define the entrypoints to our system and capture the primary use cases. We show how this layer makes it easy to build thin entrypoints to our system, whether it's a Flask API or a CLI.
dlist
Some thoughts on testing and abstractions (Chapter [3](#chapter_03_abstractions) and [5](#chapter_05_high_gear_low_gear))
After presenting the first abstraction (the Repository pattern), we take the opportunity for a general discussion of how to choose abstractions, and what their role is in choosing how our software is coupled together. After we introduce the Service Layer pattern, we talk a bit about achieving a *test pyramid* and writing unit tests at the highest possible level of abstraction.
sect3
#### [#part2](#part2){data-type="xref" xrefstyle="chap-num-title"}
dlist
Event-driven architecture (Chapters [8](#chapter_08_events_and_message_bus)-[11](#chapter_11_external_events))
We introduce three more mutually reinforcing patterns the Domain Events, Message Bus, and Handler patterns. *Domain events* are a vehicle for capturing the idea that some interactions with a system are triggers for others. We use a *message bus* to allow actions to trigger events and call appropriate *handlers*. We move on to discuss how events can be used as a pattern for integration between services in a microservices architecture. Finally, we distinguish between *commands* and *events*. Our application is now fundamentally a message-processing system.
Command-query responsibility segregation ([\[chapter_12_cqrs\]](#chapter_12_cqrs))
We present an example of *command-query responsibility segregation*, with and without events.
Dependency injection ([\[chapter_13_dependency_injection\]](#chapter_13_dependency_injection))
We tidy up our explicit and implicit dependencies and implement a simple dependency injection framework.
sect3
#### Additional Content
dlist
How do I get there from here? ([\[epilogue_1_how_to_get_there_from_here\]](#epilogue_1_how_to_get_there_from_here))
Implementing architectural patterns always looks easy when you show a simple example, starting from scratch, but many of you will probably be wondering how to apply these principles to existing software. We'll provide a few pointers in the epilogue and some links to further reading.
sect2
### Example Code and Coding Along
You're reading a book, but you'll probably agree with us when we say that the best way to learn about code is to code. We learned most of what we know from pairing with people, writing code with them, and learning by doing, and we'd like to re-create that experience as much as possible for you in this book.
As a result, we've structured the book around a single example project (although we do sometimes throw in other examples). We'll build up this project as the chapters progress, as if you've paired with us and we're explaining what we're doing and why at each step.
But to really get to grips with these patterns, you need to mess about with the code and get a feel for how it works. You'll find all the code on GitHub; each chapter has its own branch. You can find [a list](https//github.com/cosmicpython/code/branches/all) of the branches on GitHub as well.
Here are three ways you might code along with the book
ulist
- Start your own repo and try to build up the app as we do, following the examples from listings in the book, and occasionally looking to our repo for hints. A word of warning, however if you've read Harry's previous book and coded along with that, you'll find that this book requires you to figure out more on your own; you may need to lean pretty heavily on the working versions on GitHub.
- Try to apply each pattern, chapter by chapter, to your own (preferably small/toy) project, and see if you can make it work for your use case. This is high risk/high reward (and high effort besides!). It may take quite some work to get things working for the specifics of your project, but on the other hand, you're likely to learn the most.
- For less effort, in each chapter we outline an \"Exercise for the Reader,\" and point you to a GitHub location where you can download some partially finished code for the chapter with a few missing parts to write yourself.
Particularly if you're intending to apply some of these patterns in your own projects, working through a simple example is a great way to safely practice.
+-----------------------------------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|  title                         | At the very least, do a `git checkout` of the code from our repo as you read each chapter. Being able to jump in and see the code in the context of an actual working app will help answer a lot of questions as you go, and makes everything more real. You'll find instructions for how to do that at the beginning of each chapter. |
| Tip                               |                                                                                                                                                                                                                                                                                                                                        |
|                                |                                                                                                                                                                                                                                                                                                                                        |
+-----------------------------------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
sect2
### License
The code (and the online version of the book) is licensed under a Creative Commons CC BY-NC-ND license, which means you are free to copy and share it with anyone you like, for non-commercial purposes, as long as you give attribution. If you want to re-use any of the content from this book and you have any worries about the license, contact O'Reilly at [*permissions@oreilly.com*](mailtopermissions@oreilly.com){.email}.
The print edition is licensed differently; please see the copyright page.
sect2
### Conventions Used in This Book
The following typographical conventions are used in this book
dlist
*Italic*
Indicates new terms, URLs, email addresses, filenames, and file extensions.
Constant width
Used for program listings, as well as within s to refer to program elements such as variable or function names, databases, data types, environment variables, statements, and keywords.
**`Constant width bold`**
Shows commands or other text that should be typed literally by the user.
*Constant width italic*
Shows text that should be replaced with user-supplied values or by values determined by context.
+-----------------------------------+---------------------------------------------+
|  title                         |                                 |
| Tip                               | This element signifies a tip or suggestion. |
|                                |                                          |
+-----------------------------------+---------------------------------------------+
+-----------------------------------+----------------------------------------+
|  title                         |                            |
| Note                              | This element signifies a general note. |
|                                |                                     |
+-----------------------------------+----------------------------------------+
+-----------------------------------+----------------------------------------------+
|  title                         |                                  |
| Warning                           | This element indicates a warning or caution. |
|                                |                                           |
+-----------------------------------+----------------------------------------------+
sect2
### O'Reilly Online Learning
+-----------------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|  title                         |                                                                                                                                                                   |
| Note                              | For more than 40 years, [*O'Reilly Media*](http//oreilly.com){.ormhideurl} has provided technology and business training, knowledge, and insight to help companies succeed. |
|                                |                                                                                                                                                                            |
+-----------------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
Our unique network of experts and innovators share their knowledge and expertise through books, articles, conferences, and our online learning platform. O'Reilly's online learning platform gives you on-demand access to live training courses, in-depth learning paths, interactive coding environments, and a vast collection of text and video from O'Reilly and 200+ other publishers. For more information, please visit [*http//oreilly.com*](http//oreilly.com){.ormhideurl}.
sect2
### How to Contact O'Reilly
Please address comments and questions concerning this book to the publisher
- O'Reilly Media, Inc.
- 1005 Gravenstein Highway North
- Sebastopol, CA 95472
- 800-998-9938 (in the United States or Canada)
- 707-829-0515 (international or local)
- 707-829-0104 (fax)
We have a web page for this book, where we list errata, examples, and any additional information. You can access this page at [https//oreil.ly/architecture-patterns-python](https//oreil.ly/architecture-patterns-python){.bare}.
Email [*bookquestions@oreilly.com*](mailtobookquestions@oreilly.com){.email} to comment or ask technical questions about this book.
For more information about our books, courses, conferences, and news, see our website at [http//www.oreilly.com](http//www.oreilly.com){.bare}.
Find us on Facebook [http//facebook.com/oreilly](http//facebook.com/oreilly){.bare}
Follow us on Twitter [http//twitter.com/oreillymedia](http//twitter.com/oreillymedia){.bare}
Watch us on YouTube [http//www.youtube.com/oreillymedia](http//www.youtube.com/oreillymedia){.bare}
sect2
### Acknowledgments
To our tech reviewers, David Seddon, Ed Jung, and Hynek Schlawack we absolutely do not deserve you. You are all incredibly dedicated, conscientious, and rigorous. Each one of you is immensely smart, and your different points of view were both useful and complementary to each other. Thank you from the bottom of our hearts.
Gigantic thanks also to all our readers so far for their comments and suggestions Ian Cooper, Abdullah Ariff, Jonathan Meier, Gil Gonçalves, Matthieu Choplin, Ben Judson, James Gregory, Łukasz Lechowicz, Clinton Roy, Vitorino Araújo, Susan Goodbody, Josh Harwood, Daniel Butler, Liu Haibin, Jimmy Davies, Ignacio Vergara Kausel, Gaia Canestrani, Renne Rocha, pedroabi, Ashia Zawaduk, Jostein Leira, Brandon Rhodes, Jazeps Basko, simkimsia, Adrien Brunet, Sergey Nosko, Dmitry Bychkov, dayres2, programmer-ke, asjhita, Filip Lajszczak, and many more; our apologies if we missed you on this list.
Super-mega-thanks to our editor Corbin Collins for his gentle chivvying, and for being a tireless advocate of the reader. Similarly-superlative thanks to the production staff, Katherine Tozer, Sharon Wilkey, Ellen Troutman-Zaig, and Rebecca Demarest, for your dedication, professionalism, and attention to detail. This book is immeasurably improved thanks to you.
Any errors remaining in the book are our own, naturally.
------------------------------------------------------------------------
[1](#_footnoteref_1). `python -c "import this"`
Last updated 2025-09-02 102309 +0800