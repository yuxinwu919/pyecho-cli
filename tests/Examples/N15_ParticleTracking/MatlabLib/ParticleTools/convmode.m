function C=convmode(A,B,mode)
C=[];
if mode==2, C=conv(A,B); end;
if mode==1, 
    i=floor(length(B)*0.5); 
    n=length(A);
    C1=conv(A,B); 
    C(1:n)=C1(1+i:n+i);
end;
