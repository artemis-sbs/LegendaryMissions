# Artemis Markdown language
The Artemis Markdown language is based on markdown

It uses syntax based on the markdown language
The abbreviation AMD will be used to refer to Artemis Markdown

AMD does not support all of markdown
<br>
AMD uses markdown syntax where it makes sense
<br>
AM adds syntax
<br>
AMD repurposes some markdown concepts to 
<br>
e.g. The table of contents is used to build a Document Tree NOT used for in document hyperlinks


## Comments
AMD Supports comment. 
This is not standard Markdown, but some variants support it

``` C
// When you see this it is a comment
// Comments are the whole line and must start at the beginning of the line
```


## Headings

AMD Supports heading as in markdowm. A line starting with a series of # denotes a heading. The number of # represents the heading level.

``` md
# Heading level 1
## heading Level 2
###  heading Level 3
###  heading Level 4
```

### Heading for the Table of contents
AMD Adds a extension to markdown for building a document structure.

By using the link syntax the link it defines a entry in the table of contents.

The table of content sections will be separate sections in the document viewer. Heading level will denote children of a section.

``` md
# [Kills](kills)
## [Kill 25 Enemy](kills25)
## [Kill 50 Enemy](kills50)
```

Heading need to new line to separate it from its contents.

## Data sections
AMD Supports adding data to the underlying data of the document. The section in between lines marked with multiple dashes at least 3.

Meta data is not standard in markdown.
Many variants allow this syntax at the top of the document.

AMD Allows meta data sections anywhere in the document.
The meta data will be added to the current heading data.

This data will be available to the data exposed. For example the data will be connect to a Quest element and can be accessed and changed by script.

``` yaml
---
some_data: 123
---
```

## Links
Inline links for images, faces and file start with ![] followed by the link in parentheses.

### Image links
Image links specify a key from the image atlas.
This can be a file path. Or a key defined in the image atlas allowing for subimages.

``` md
![](image:operator)
```

Images support two configuration options:

- scale
- fill

The link follows url syntax. So the optional arguments start with a ? then a key = value additional arguments are separated with an ampersand.


``` md
![](image:operator?scale=0.5&fill=center)
```


### Face links
Face link inserts a face.

Optional properties:

- align: left, right, center
- height: in pixels

``` md
![](face:ter #964b00 8 1;ter #968b00 3 0;ter #968b00 4 0;ter #968b00 5 2;ter #fff 3 5;ter #964b00 8 4;?align=left)
```

### Ship links
Ship link inserts a ship using its ship data key.

Optional properties:

- align: left, right, center
- height: in pixels

``` md
ship:tsn_light_cruiser?height=100&align=center
```

### style links
Styles can be define styles.

note: older method had style define by !$name and references via $name


``` md
[p1]: style:font:gui-2;color:blue;justify:right;
[bold]: style:font:gui-4;color:yellow;justify:center;
```

Old style (deprecated)
``` md
!$p1 font:gui-2;color:blue;justify:right;
```


Style can be referenced in the document via

``` md
[][p1] This is in p1 format
```

This non-standard shortcut works as well

``` md
[p1] This is in p1 format too
```

Old style (deprecated)
``` md
$p1 This is formatted with p1
```



A style link without the key value will try to load styles Referencing a file or script inserted styles set

``` 
[]: style:some_styles
[]: style:folder/some_styles
```



### Reference Definition links


``` md
[logo]: image:operator
[captain]: face:ter #964b00 8 1;ter #968b00 3 0;ter #968b00 4 0;ter #968b00 5 2;ter #fff 3 5;ter #964b00 8 4;?align=left
```


### Referencing a defined link

``` md
![][captain]
![][logo]
```

Non standard short version

``` md
![captain]
![logo]
```


## Line breaks

``` html
<br>
<br/>
```



## Example
This is an example of a quest document.


``` md
# [Quest One](quest1)

Track the number of quest1

[](style:font:gui-2;color:blue;background:white) This is white on blue

[](style:font:gui-2;color:green;background:white) 
This is green on white
still is
and now

but not now

# [Quest Two](quest2)

Track the number of quest2

## This is headind 2

# Title

### This is H3

    
1. One
1. Two
1. Three

## Example sub image

![](image:test2?scale=0.5&fill=center)


## Ship

![](ship:tsn_light_cruiser?height=100&align=center)

## Face

![](face:ter #964b00 8 1;ter #968b00 3 0;ter #968b00 4 0;ter #968b00 5 2;ter #fff 3 5;ter #964b00 8 4;?align=left)

### This is H3


- Blue
- Red 
- Green
- Test

![](image:test?scale=0.25&fill=center)

![](image:ball?scale=0.25&fill=center&color=blue)




### This is H3

# Heading one

### Heading 3

1. This
1. Is
1. ordered

- This
- is 
- unordered

# End
        

# [Kills](kills)

Track the number of kills.
This has sub quests

## [Kill 25 enemies](kills25?state=COMPLETE)

A quest that will be complete after 25 kills

## [Kill 50 enemies](kills50)

A quest that will be complete after 50 kills

## [Kill 100 enemies](kills100?state=FAILED)

A quest that will be complete after 100 kills

## [Kill 200 enemies](kills200?state=SECRET)

A quest that will be complete after 200 kills

```
