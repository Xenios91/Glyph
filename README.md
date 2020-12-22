# Glyph

[![Codacy Badge](https://api.codacy.com/project/badge/Grade/97620c92ce9e42e49b67029f4b3396ac)](https://app.codacy.com/gh/Xenios91/Glyph?utm_source=github.com&utm_medium=referral&utm_content=Xenios91/Glyph&utm_campaign=Badge_Grade)


## A architecture independant binary analysis tool for fingerprinting functions through NLP.

Glyph allows you to upload an ELF binary (32 & 64 bit) for function fingerprinting, upon analysis, a web based function symbol table will be created.


![Main Page](https://i.imgur.com/SQni1yx.png)

## Why not use assembly?

Deciding how we wanted instructions represented was one of the biggest difficulties for the Glyph project. At one side of the argument, one could argue using disassembly is the absolute best way to finger print functions, after all, disassembly is the lowest form of instructions we have before they are processed through the assembler where it is converted to machine language. Using disassembly would also give the most data to for Glyph to work with, this could drastically increase the accuracy of NLP due to machine learning in general performing better with more data. Disassembly has two downsides in this regard though, one being it is architecture specific, meaning ARM instruction sets when a binary is disassembled will look drastically different than x86 binaries disassembled due to the CPU architecture being completely different, with different registers and an overall reduced instruction set in ARM, this also leaves the potential for issues to occur due to differences between different compilers utilized. In figure 4 below, you can see on the top, x86-64-bit instructions and below it arm instructions for the same helloworld.c application dynamically compiled and not stripped. As you can see, the instruction sets are so different, it would be incredibly difficult for a machine learning model to determine these to be identical functions without additional training occurring.

## Why not IR?

Often during compilation IR (intermediary representation) is utilized to make it easier to convert a high-level language into a lower level language. In reverse engineering this also occurs, tools like SLEIGH in Ghidra convert assembly instructions into IR (Ghidra refers to it as Pcode) which allows for it to then convert IR into C for its decompilation capabilities. IR can be incredibly powerful and removes the issue shown above when it comes to instruction sets being drastically different, it also increases data about a function giving our machine learning model more to work with, which could, and most likely would increase accuracy of function fingerprinting. There is one issue however, IR is not offset independent. When IR is generated and observed, offsets and addresses of the instructions will be included in the data, which will essentially add data that is dependent on the binary being examined, the architecture, and even the compiler being utilized. While offsets in IR do not muddy up our data as much as analyzing disassembled binaries would, it still leaves enough data that can potentially create chaos in the instructions being analyzed, ensuring some instructions when tokenized are never ever found again in similar functions.

