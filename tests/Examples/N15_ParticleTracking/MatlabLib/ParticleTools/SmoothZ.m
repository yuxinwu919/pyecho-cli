function Zout=SmoothZ(Zin,M)
if M>0,
  [Zout, inds]=sortrows(Zin); 
  N=length(Zin);
  S(N+1)=0; S(1)=0; for i=1:N, S(i+1)=S(i)+Zout(i); end
  Zout2(N)=Zout(N);
  Zout2(1)=Zout(1);
  for i=2:N-1
    m=min(i-1,N-i);
    m=floor(f(0.5*m,0.5*M)+0.500001);
    Zout2(i)=(S(i+m+1)-S(i-m))/(2*m+1);
  end
  Zout(inds,:)=Zout2;
else
    Zout=Zin;
end 
end

function y=f(x,A)
  if x<2*A
    y=x-x*x/(4*A);
  else
    y=A;
  end
end