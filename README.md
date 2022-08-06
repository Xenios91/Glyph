# Glyph v1.0.0

## An architecture independent binary analysis tool for fingerprinting functions through NLP

### Version 1.0.0

Glyph API Documentation: https://xenios91.github.io/Glyph-API-Docs/

Ghidra Script
https://github.com/Xenios91/Glyph-Ghidra

## About

Reverse engineering is an important task performed by security researchers to identify vulnerable functions and malicious functions in IoT (Internet of Things) devices that are often shared across multiple devices of many system architectures. Common techniques to currently identify the reuse of these functions do not perform cross-architecture identification unless specific data such as unique strings are identified that may be of use in identifying a piece of code. Utilizing natural language processing techniques, Glyph allows you to upload an ELF binary (32 & 64 bit) for cross-architecture function fingerprinting, upon analysis, a web-based function symbol table will be created and presented to the user to aid in their analysis of binary executables/shared objects.

![Main Page](https://i.imgur.com/Gb9OFNN.png)

## Why not use assembly

Deciding how we wanted instructions represented was one of the biggest difficulties for the Glyph project. At one side of the argument, one could argue using disassembly is the absolute best way to finger print functions, after all, disassembly is the lowest form of instructions we have before they are processed through the assembler where it is converted to machine language. Using disassembly would also give the most data to for Glyph to work with, this could drastically increase the accuracy of NLP due to machine learning in general performing better with more data. Disassembly has two downsides in this regard though, one being it is architecture specific, meaning ARM instruction sets when a binary is disassembled will look drastically different than x86 binaries disassembled due to the CPU architecture being completely different, with different registers and an overall reduced instruction set in ARM, this also leaves the potential for issues to occur due to differences between different compilers utilized.

## Why not intermediary representation

Often during compilation IR (intermediary representation) is utilized to make it easier to convert a high-level language into a lower level language. In reverse engineering this also occurs, tools like SLEIGH in Ghidra convert assembly instructions into IR (Ghidra refers to it as Pcode) which allows for it to then convert IR into C for its decompilation capabilities. IR can be incredibly powerful and removes the issue shown above when it comes to instruction sets being drastically different, it also increases data about a function giving our machine learning model more to work with, which could, and most likely would increase accuracy of function fingerprinting. There is one issue however, IR is highly dependant on basic block structure. When IR is generated and observed, it will generate code that is dependant on the type of architecture the binary was compiled on, which will essentially add data that is dependent on the binary being examined, the architecture, and even the compiler being utilized. While these basic block structures in IR do not muddy up our data as much as analyzing disassembled binaries would, it still leaves enough additional complexities that can potentially create chaos in the instructions being analyzed, ensuring some instructions when tokenized are never ever found again in similar functions.


## Glyph Issues

Most of Glyphs issues currently stem from Ghidra’s results, and while we find Ghidra to be a great tool, it’s not without issue when it comes to both identifying functions and performing decompilation. Ghidra at times may fail to decompile code properly, resulting in either partially decompiled functions, improper values identified such as incorrect return types (as discussed previously), incorrect parameters, or functions not decompiling at all. When some of these issues occur, decompilation will leave an error message stating the issue, which will be then utilized by Glyph for its machine learning model. Due to this error message being sometimes placed in a functions token list along with C code and being utilized for identifying functions, it results in inaccuracies occurring. 

