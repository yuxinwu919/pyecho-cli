function ChangeNParameters(taskfile,parameter,svalue)
    N=length(svalue);
    global OS_LINUX
    tfile='mytempfile.txt';
    fin=fopen(taskfile,'rt');
    fout=fopen(tfile,'wt');
    i=1;
    while feof(fin) == 0,
       line = fgets(fin);
       if length(strfind(line,parameter))>0,
            line=sprintf('%s = %s\n',parameter,svalue{i} ) ;
            i=mod(i,N)+1;
       end;
       fprintf(fout,'%s',line);
    end;
    fclose(fout);
    fclose(fin);
    if OS_LINUX, cmd='mv', else cmd='move'; end;
    system([cmd ' ' tfile ' ' taskfile]);

