function y1=myinterp1(x,y,n0,x1,n1)
j=0;
for i=1:n1,
    x10=x1(i);
    y1(i)=y(1);
    if x10>=x(n0), 
        y1(i)=y(n0);
    else
        while (x(j+1)<x10),
            j=j+1;
        end;
        if j>0,
            y1(i)=y(j)+(y(j+1)-y(j))*(x10-x(j))/(x(j+1)-x(j));
        end;
    end;
end;
