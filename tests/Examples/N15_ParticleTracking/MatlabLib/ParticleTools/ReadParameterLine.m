function svalue=ReadParameterLine(taskfile,parameter)
    fin=fopen(taskfile,'rt');
    while feof(fin) == 0,
       sline = fgets(fin);
       k=strfind(sline,parameter);
       if length(k)==0, 
           k=0;
       else
          svalue=strtrim(sline);
       end;
    end;
    fclose(fin);
    
