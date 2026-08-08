function ChangeParameter(taskfile,parameter,svalue)
    global OS_LINUX
    tfile='mytempfile.txt';
    fin=fopen(taskfile,'rt');
    fout=fopen(tfile,'wt');
    while feof(fin) == 0,
       sline = fgets(fin);
       k=strfind(sline,parameter);
       if length(k)==0, 
       else
            if k(1)>1,
               sline=[sline(1:k(1)-1) sprintf('%s = %s\n',parameter,svalue )] ;
            else
                sline=[sprintf('%s = %s\n',parameter,svalue )] ;
            end;
       end;
       fprintf(fout,'%s',sline);
    end;
    fclose(fout);
    fclose(fin);
    if OS_LINUX, cmd='mv', else cmd='move'; end;
    system([cmd ' ' tfile ' ' taskfile]);

